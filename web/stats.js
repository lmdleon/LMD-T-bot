// stats.js - Web interface for displaying daily trade statistics

document.addEventListener('DOMContentLoaded', function() {
    const statusElement = document.getElementById('status');
    const statsContainer = document.getElementById('daily-stats-container');
    const noDataElement = document.getElementById('no-data');
    
    // Format date to readable string
    function formatDate(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric' });
    }
    
    // Format number with spaces as thousands separator
    function formatNumber(num, decimals = 2) {
        if (num === null || num === undefined || isNaN(num)) return 'N/A';
        const formatted = num.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
        return formatted;
    }
    
    // Format currency with color based on positive/negative (except commissions)
    function formatCurrency(num, isCommission = false) {
        if (num === null || num === undefined || isNaN(num)) return 'N/A';
        const formatted = formatNumber(num, 2);
        
        // Don't color commissions
        if (isCommission) {
            return `<span>${formatted}</span>`;
        }
        
        if (num >= 0) {
            return `<span class="currency-positive">${formatted}</span>`;
        } else {
            return `<span class="currency-negative">${formatted}</span>`;
        }
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
    
    // Fetch daily stats from API
    async function fetchDailyStats() {
        statusElement.textContent = 'Загрузка данных...';
        
        try {
            const response = await fetch('/api/stats/daily');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                statusElement.textContent = `Ошибка: ${data.error}`;
                return;
            }
            
            // Clear container
            statsContainer.innerHTML = '';
            
            if (!data.daily_stats || data.daily_stats.length === 0) {
                noDataElement.classList.remove('hidden');
                statusElement.textContent = 'Нет данных в базе';
                return;
            }
            
            noDataElement.classList.add('hidden');
            statusElement.textContent = `Загружено записей: ${data.daily_stats.length}`;
            
            // Group stats by date
            const groupedStats = {};
            data.daily_stats.forEach(stat => {
                if (!groupedStats[stat.date]) {
                    groupedStats[stat.date] = [];
                }
                groupedStats[stat.date].push(stat);
            });
            
            // Render accordion for each date
            const dates = Object.keys(groupedStats).sort((a, b) => b.localeCompare(a)); // Sort descending
            
            dates.forEach(date => {
                const statsForDate = groupedStats[date];
                
                // Calculate totals for the day
                const dayTrades = statsForDate.reduce((sum, s) => sum + s.trade_count, 0);
                const dayCommissions = statsForDate.reduce((sum, s) => sum + s.total_commissions, 0);
                const dayAmounts = statsForDate.reduce((sum, s) => sum + s.total_amounts, 0);
                const dayResult = statsForDate.reduce((sum, s) => sum + s.result, 0);
                
                // Create accordion header
                const accordionHeader = document.createElement('div');
                accordionHeader.className = 'accordion-header';
                
                // Color the day result in header
                const dayResultClass = dayResult >= 0 ? 'currency-positive' : 'currency-negative';
                
                accordionHeader.innerHTML = `
                    <span class="accordion-icon">▶</span>
                    <span class="accordion-date">${formatDate(date)}</span>
                    <span class="accordion-summary">
                        Сделок: ${dayTrades} | 
                        Комиссии: ${formatCurrency(dayCommissions, true)} | 
                        Результат: <span class="${dayResultClass}">${formatCurrency(dayResult)}</span>
                    </span>
                `;
                
                // Create accordion content
                const accordionContent = document.createElement('div');
                accordionContent.className = 'accordion-content';
                accordionContent.style.display = 'none';
                
                let itemsHtml = '';
                statsForDate.forEach(stat => {
                    itemsHtml += `
                        <tr>
                            <td><code>${stat.figi}</code></td>
                            <td>${stat.instrument_name}</td>
                            <td>${stat.trade_count}</td>
                            <td>${formatCurrency(stat.total_commissions, true)}</td>
                            <td>${formatCurrency(stat.total_amounts)}</td>
                            <td class="result-cell">${formatCurrency(stat.result)}</td>
                        </tr>
                    `;
                });
                
                accordionContent.innerHTML = `
                    <table class="stats-table">
                        <thead>
                            <tr>
                                <th>FIGI</th>
                                <th>Актив</th>
                                <th>Кол-во сделок</th>
                                <th>Сумма комиссий</th>
                                <th>Результат без учета комиссии</th>
                                <th>Результат</th>
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
                
                statsContainer.appendChild(accordionItem);
            });
            
            // Update total summary
            document.getElementById('total-trades').textContent = data.total_summary.total_trades;
            document.getElementById('total-commissions').textContent = formatNumber(data.total_summary.total_commissions, 2);
            document.getElementById('total-amounts').textContent = formatNumber(data.total_summary.total_amounts, 2);
            
            const totalResultEl = document.getElementById('total-result');
            totalResultEl.textContent = formatNumber(data.total_summary.total_result, 2);
            if (data.total_summary.total_result >= 0) {
                totalResultEl.className = 'summary-value result-positive';
            } else {
                totalResultEl.className = 'summary-value result-negative';
            }
            
        } catch (error) {
            console.error('Error fetching daily stats:', error);
            statusElement.textContent = `Ошибка загрузки: ${error.message}`;
        }
    }
    
    // Initial fetch
    fetchDailyStats();
    
    // Auto-refresh every 30 seconds
    setInterval(fetchDailyStats, 30000);
});
