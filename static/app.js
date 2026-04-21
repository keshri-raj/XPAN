document.addEventListener('DOMContentLoaded', () => {
    const runBtn = document.getElementById('run-btn');
    const scenarioSel = document.getElementById('scenario');
    const strategySel = document.getElementById('strategy');
    const loadingEl = document.getElementById('loading');
    const resultsEl = document.getElementById('results');
    const metricsGrid = document.getElementById('metrics-grid');

    const metricsToDisplay = [
        { key: 'gap_free', label: 'Gap-Free Switch', type: 'bool' },
        { key: 'cold_switches', label: 'Cold Switches', type: 'lower_is_better' },
        { key: 'interruptions_ms', label: 'Audio Interruption (ms)', type: 'lower_is_better' },
        { key: 'energy_mj', label: 'Total Energy (mJ)', type: 'lower_is_better' },
        { key: 'whc_standby_energy_mj', label: 'Prewarm Energy (mJ)', type: 'lower_is_better' },
        { key: 'unnecessary_prewarm_events', label: 'False Prewarms', type: 'lower_is_better' },
        { key: 'average_latency_ms', label: 'Average Latency (ms)', type: 'lower_is_better' },
        { key: 'handovers', label: 'Total Handovers', type: 'lower_is_better' }
    ];

    runBtn.addEventListener('click', async () => {
        const scenario = scenarioSel.value;
        const strategy = strategySel.value;

        resultsEl.classList.add('hidden');
        loadingEl.classList.remove('hidden');

        try {
            const res = await fetch(`/api/compare?scenario=${scenario}&strategy=${strategy}`);
            const data = await res.json();
            
            if(data.error) {
                alert("Simulation Error: " + data.error);
                loadingEl.classList.add('hidden');
                return;
            }

            renderMetrics(data.reactive, data.predictive);
            loadingEl.classList.add('hidden');
            resultsEl.classList.remove('hidden');
        } catch (e) {
            alert("Error fetching data.");
            loadingEl.classList.add('hidden');
        }
    });

    function renderMetrics(reactive, predictive) {
        metricsGrid.innerHTML = '';
        
        metricsToDisplay.forEach(m => {
            const rVal = reactive[m.key];
            const pVal = predictive[m.key];
            
            let diffClass = 'diff-neutral';
            let diffText = 'Same';
            
            if(m.type === 'lower_is_better') {
                if (pVal < rVal) { diffClass = 'diff-better'; diffText = `▼ ${Math.abs(rVal - pVal).toFixed(1)}`; }
                else if (pVal > rVal) { diffClass = 'diff-worse'; diffText = `▲ ${Math.abs(pVal - rVal).toFixed(1)}`; }
            } else if (m.type === 'bool') {
                if (pVal > rVal) { diffClass = 'diff-better'; diffText = 'Better'; }
                else if (pVal < rVal) { diffClass = 'diff-worse'; diffText = 'Worse'; }
            }

            const card = document.createElement('div');
            card.className = 'metric-card glass-panel';
            
            let rDisplay = typeof rVal === 'number' ? rVal.toFixed(1) : rVal;
            let pDisplay = typeof pVal === 'number' ? pVal.toFixed(1) : pVal;
            if(m.type === 'bool') {
                rDisplay = rVal ? "Yes" : "No";
                pDisplay = pVal ? "Yes" : "No";
            }

            card.innerHTML = `
                <div class="metric-header"><h3>${m.label}</h3></div>
                <div class="metric-body">
                    <div class="metric-val">
                        <span>Reactive</span>
                        <span>${rDisplay}</span>
                    </div>
                    <div class="metric-val">
                        <span>Predictive</span>
                        <span>${pDisplay}</span>
                    </div>
                    <div class="diff-badge ${diffClass}">${diffText}</div>
                </div>
            `;
            metricsGrid.appendChild(card);
        });
    }
});
