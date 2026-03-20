// app.js - Web interface for displaying trades data

document.addEventListener('DOMContentLoaded', function() {
    const statusElement = document.getElementById('status');
    const tradesBody = document.getElementById('trades-body');
    const noDataElement = document.getElementById('no-data');
    
    // Format date to readable string
    function formatDate(dateString) {
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
            
            // Clear table
            tradesBody.innerHTML = '';
            
            if (!data.trades || data.trades.length === 0) {
                noDataElement.classList.remove('hidden');
                statusElement.textContent = 'Нет данных в базе';
                return;
            }
            
            noDataElement.classList.add('hidden');
            statusElement.textContent = `Загружено сделок: ${data.trades.length}`;
            
            // Render trades
            data.trades.forEach(trade => {
                const row = document.createElement('tr');
                
                row.innerHTML = `
                    <td><code>${trade.id || 'N/A'}</code></td>
                    <td>${trade.instrument_name || 'N/A'}</td>
                    <td>${getDirectionBadge(trade.direction)}</td>
                    <td>${trade.quantity || 0}</td>
                    <td>${formatDate(trade.order_datetime)}</td>
                    <td>${formatNumber(trade.initial_commission, 2)}</td>
                    <td>${formatNumber(trade.total_order_amount, 2)}</td>
                `;
                
                tradesBody.appendChild(row);
            });
            
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
