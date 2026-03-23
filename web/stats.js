// stats.js - Web interface for displaying daily trade statistics

document.addEventListener('DOMContentLoaded', function() {
    const statusElement = document.getElementById('status');
    const statsContainer = document.getElementById('daily-stats-container');
    const noDataElement = document.getElementById('no-data');
    const stopLossSection = document.getElementById('stop-loss-section');
    const stopLossContainer = document.getElementById('stop-loss-container');
    const noStopLossDataElement = document.getElementById('no-stop-loss-data');
    
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
        const content = item.querySelector('.accordion-content, .stop-loss-accordion-content');
        const icon = item.querySelector('.accordion-icon, .stop-loss-accordion-icon');
        
        if (content && (content.style.display === 'none' || !content.style.display)) {
            content.style.display = 'block';
            if (icon) icon.textContent = '▼';
            item.classList.add('active');
        } else if (content) {
            content.style.display = 'none';
            if (icon) icon.textContent = '▶';
            item.classList.remove('active');
        }
    }
    
    // Fetch stop loss triggers from API
    async function fetchStopLossTriggers() {
        try {
            const response = await fetch('/api/stop-loss/daily');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Clear container
            stopLossContainer.innerHTML = '';
            
            if (!data.daily_triggers || data.daily_triggers.length === 0) {
                noStopLossDataElement.classList.remove('hidden');
                stopLossSection.style.display = 'none';
                return;
            }
            
            noStopLossDataElement.classList.add('hidden');
            stopLossSection.style.display = 'block';
            
            // Update total summary
            document.getElementById('stop-loss-total-dates').textContent = data.total_summary.total_dates;
            document.getElementById('stop-loss-total-triggers').textContent = data.total_summary.total_triggers;
            
            // Render accordion for each date with triggers
            const dates = data.daily_triggers.map(t => t.date).sort((a, b) => b.localeCompare(a));
            
            dates.forEach(date => {
                const triggersForDate = data.daily_triggers.find(t => t.date === date);
                
                if (!triggersForDate) return;
                
                // Create accordion header
                const accordionHeader = document.createElement('div');
                accordionHeader.className = 'stop-loss-accordion-header';
                
                accordionHeader.innerHTML = `
                    <span class="stop-loss-accordion-icon">▶</span>
                    <span class="stop-loss-accordion-date">${formatDate(date)}</span>
                    <span class="stop-loss-accordion-summary">
                        Сработало стоп-лоссов: ${triggersForDate.trigger_count}
                    </span>
                `;
                
                // Create accordion content
                const accordionContent = document.createElement('div');
                accordionContent.className = 'stop-loss-accordion-content';
                accordionContent.style.display = 'none';
                
                let itemsHtml = '';
                triggersForDate.figis.forEach(figi => {
                    itemsHtml += `
                        <tr>
                            <td><code>${figi}</code></td>
                            <td>Сработал стоп-лосс</td>
                        </tr>
                    `;
                });
                
                accordionContent.innerHTML = `
                    <table class="stats-table">
                        <thead>
                            <tr>
                                <th>FIGI</th>
                                <th>Статус</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${itemsHtml}
                        </tbody>
                    </table>
                `;
                
                // Create accordion item container
                const accordionItem = document.createElement('div');
                accordionItem.className = 'stop-loss-accordion-item';
                accordionItem.appendChild(accordionHeader);
                accordionItem.appendChild(accordionContent);
                
                // Add click event to toggle
                accordionHeader.addEventListener('click', () => toggleAccordion(accordionItem));
                
                stopLossContainer.appendChild(accordionItem);
            });
            
        } catch (error) {
            console.error('Error fetching stop loss triggers:', error);
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
            } else {
                noDataElement.classList.add('hidden');
                statusElement.textContent = `Загружено записей: ${data.daily_stats.length}`;
            }
            
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
        
        // Also fetch stop loss triggers
        await fetchStopLossTriggers();
    }
    
    // Initial fetch
    fetchDailyStats();
    
    // Auto-refresh every 30 seconds
    setInterval(async () => {
        await fetchDailyStats();
    }, 30000);
});
