// app.js - Web interface for displaying trades data

document.addEventListener('DOMContentLoaded', function() {
    const statusElement = document.getElementById('status');
    const tradesContainer = document.getElementById('trades-container');
    const noDataElement = document.getElementById('no-data');
    
    // Format date to readable string
    function formatDate(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric' });
    }
    
    // Format datetime to readable string with time
    function formatDateTime(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('ru-RU') + ' ' + date.toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    // Format number with spaces as thousands separator
    function formatNumber(num, decimals = 2) {
        if (num === null || num === undefined || isNaN(num)) return 'N/A';
        return num.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    }
    
    // Get direction badge HTML - 1=Buy, 2=Sell
    function getDirectionBadge(direction) {
        const dir = direction ? String(direction).trim() : '';
        if (dir === '1') {
            return `<span class="direction-badge direction-buy">Покупка</span>`;
        } else if (dir === '2') {
            return `<span class="direction-badge direction-sell">Продажа</span>`;
        }
        return `<span class="direction-badge" style="background: #e2e3e5; color: #41464b;">${direction || 'N/A'}</span>`;
    }
    
    // Toggle accordion item
    function toggleAccordion(item) {
        const content = item.querySelector('.accordion-content');
        const icon = item.querySelector('.accordion-icon');
        
        if (content.style.display === 'none' || !content.style.display) {
            content.style.display = 'block';
            icon.textContent = '▼';
            item.classList.add('active');
        } else {
            content.style.display = 'none';
            icon.textContent = '▶';
            item.classList.remove('active');
        }
    }
    
    // Fetch trades from API
    async function fetchTrades() {
        statusElement.textContent = 'Загрузка данных...';
        
        try {
            const response = await fetch('/api/trades');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                statusElement.textContent = `Ошибка: ${data.error}`;
                return;
            }
            
            // Clear container
            tradesContainer.innerHTML = '';
            
            if (!data.trades || data.trades.length === 0) {
                noDataElement.classList.remove('hidden');
                statusElement.textContent = 'Нет данных в базе';
                return;
            }
            
            noDataElement.classList.add('hidden');
            statusElement.textContent = `Загружено сделок: ${data.trades.length}`;
            
            // Group trades by date
            const groupedTrades = {};
            data.trades.forEach(trade => {
                // Extract just the date part (YYYY-MM-DD)
                const datePart = trade.order_datetime ? trade.order_datetime.split('T')[0] : 'Unknown';
                if (!groupedTrades[datePart]) {
                    groupedTrades[datePart] = [];
                }
                groupedTrades[datePart].push(trade);
            });
            
            // Sort dates descending (newest first)
            const dates = Object.keys(groupedTrades).sort((a, b) => b.localeCompare(a));
            
            let totalTrades = 0;
            let totalCommissions = 0;
            
            // Render accordion for each date
            dates.forEach(date => {
                const tradesForDate = groupedTrades[date];
                
                // Calculate totals for the day
                const dayTrades = tradesForDate.length;
                const dayCommissions = tradesForDate.reduce((sum, t) => sum + (t.initial_commission || 0), 0);
                
                totalTrades += dayTrades;
                totalCommissions += dayCommissions;
                
                // Create accordion header
                const accordionHeader = document.createElement('div');
                accordionHeader.className = 'accordion-header';
                
                accordionHeader.innerHTML = `
                    <span class="accordion-icon">▶</span>
                    <span class="accordion-date">${formatDate(date)}</span>
                    <span class="accordion-summary">
                        Сделок: ${dayTrades} | 
                        Комиссии: ${formatNumber(dayCommissions, 2)}
                    </span>
                `;
                
                // Create accordion content
                const accordionContent = document.createElement('div');
                accordionContent.className = 'accordion-content';
                accordionContent.style.display = 'none';
                
                let itemsHtml = '';
                tradesForDate.forEach(trade => {
                    itemsHtml += `
                        <tr>
                            <td><code>${trade.id || 'N/A'}</code></td>
                            <td>${trade.instrument_name || 'N/A'}</td>
                            <td>${getDirectionBadge(trade.direction)}</td>
                            <td>${trade.quantity || 0}</td>
                            <td>${formatDateTime(trade.order_datetime)}</td>
                            <td>${formatNumber(trade.initial_commission, 2)}</td>
                            <td>${formatNumber(trade.total_order_amount, 2)}</td>
                        </tr>
                    `;
                });
                
                accordionContent.innerHTML = `
                    <table class="stats-table">
                        <thead>
                            <tr>
                                <th>ID Заказа</th>
                                <th>Название</th>
                                <th>Направление</th>
                                <th>Количество</th>
                                <th>Дата и время</th>
                                <th>Комиссия</th>
                                <th>Общая сумма</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${itemsHtml}
                        </tbody>
                    </table>
                `;
                
                // Create accordion item container
                const accordionItem = document.createElement('div');
                accordionItem.className = 'accordion-item';
                accordionItem.appendChild(accordionHeader);
                accordionItem.appendChild(accordionContent);
                
                // Add click event to toggle
                accordionHeader.addEventListener('click', () => toggleAccordion(accordionItem));
                
                tradesContainer.appendChild(accordionItem);
            });
            
            // Update total summary
            document.getElementById('total-trades').textContent = totalTrades;
            document.getElementById('total-commissions').textContent = formatNumber(totalCommissions, 2);
            
        } catch (error) {
            console.error('Error fetching trades:', error);
            statusElement.textContent = `Ошибка загрузки: ${error.message}`;
        }
    }
    
    // Initial fetch
    fetchTrades();
    
    // Auto-refresh every 30 seconds
    setInterval(fetchTrades, 30000);
});
