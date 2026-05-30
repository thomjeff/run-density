(() => {
    // Baseline state (Issue #676, #756)
    // targetConfigId = Race Configuration package (write destination)
    // runnerSourceId = package to read *_runners.csv from (dropdown)
    let baselineState = {
        runId: null,
        baselineMetrics: null,
        selectedFiles: [],
        dataDir: null,
        configDir: null,
        targetConfigId: null,
        runnerSourceId: null,
        controlVariables: null,
        newBaselineMetrics: null,
        reportsPath: null
    };

    function getConfigIdFromUrl() {
        const params = new URLSearchParams(window.location.search);
        const raw = params.get('config_id');
        return raw ? raw.trim() : null;
    }

    function isRaceConfigurationPage() {
        return !!document.getElementById('race-config-workspace');
    }

    /** Active config package to write generated runner CSVs into (#756). */
    function getTargetConfigId() {
        if (baselineState.targetConfigId) {
            return baselineState.targetConfigId;
        }
        if (isRaceConfigurationPage()) {
            return getConfigIdFromUrl();
        }
        return null;
    }

    function getRunnerSourceId() {
        const fromState = baselineState.runnerSourceId;
        if (fromState) return fromState;
        const select = document.getElementById('baseline-config-dir');
        if (!select) return null;
        const value = (select.value || '').trim();
        return value || null;
    }

    function baselineApiPayload(extra) {
        const payload = Object.assign({}, extra || {});
        const sourceId = getRunnerSourceId();
        if (sourceId) {
            payload.config_id = sourceId;
        } else if (baselineState.configDir) {
            payload.config_dir = baselineState.configDir;
        }
        if (baselineState.dataDir) {
            payload.data_dir = baselineState.dataDir;
        }
        return payload;
    }

    function createFilesPayload(extra) {
        const payload = baselineApiPayload(extra);
        const targetId = getTargetConfigId();
        if (targetId) {
            payload.target_config_id = targetId;
        }
        return payload;
    }

    let listenersBound = false;

    function setSourcePickerVisible(show) {
        const el = document.getElementById('baseline-config-selection');
        if (el) el.style.display = show ? 'block' : 'none';
    }

    function setEmptyPackageHintVisible(show) {
        const el = document.getElementById('baseline-empty-package-hint');
        if (el) el.style.display = show ? 'block' : 'none';
    }

    function setChangeSourceLinkVisible(show) {
        const el = document.getElementById('baseline-change-source-wrap');
        if (el) el.style.display = show ? 'block' : 'none';
    }

    function setStep1Visible(show) {
        const el = document.getElementById('baseline-step1');
        if (el) el.style.display = show ? 'block' : 'none';
    }

    function updateSourceSummary(sourceId, fromOwnPackage) {
        const el = document.getElementById('baseline-source-summary');
        if (!el || !sourceId) return;
        if (fromOwnPackage) {
            el.textContent = 'Using runner files in this config package.';
        } else {
            el.textContent = 'Using runner files from: ' + sourceId;
        }
    }

    async function fetchPackageRunnerFiles(configId) {
        if (!configId) return [];
        try {
            const resp = await fetch(
                '/api/config/packages/' + encodeURIComponent(configId) + '/files?extension=csv',
                { credentials: 'same-origin' }
            );
            if (!resp.ok) return [];
            const data = await resp.json();
            return (data.files || []).filter(function (f) {
                return f.endsWith('_runners.csv');
            });
        } catch (e) {
            console.error('Error loading package runner files:', e);
            return [];
        }
    }

    function appendRunnerSourceOption(selectEl, configId, label) {
        const opt = document.createElement('option');
        opt.value = configId;
        opt.textContent = label;
        selectEl.appendChild(opt);
    }

    async function loadPackagesWithRunners(selectEl, excludeConfigId, placeholderText) {
        if (!selectEl) return 0;
        const placeholder = placeholderText || 'Select a package with runner files…';
        selectEl.innerHTML = '<option value="">' + placeholder + '</option>';
        let added = 0;

        try {
            const response = await fetch('/api/config/packages', { credentials: 'same-origin' });
            if (response.ok) {
                const data = await response.json();
                (data.packages || []).forEach(function (pkg) {
                    if (!pkg.readiness || !pkg.readiness.has_runners) return;
                    if (excludeConfigId && pkg.config_id === excludeConfigId) return;
                    const legacy = pkg.legacy ? ' (legacy)' : '';
                    appendRunnerSourceOption(
                        selectEl,
                        pkg.config_id,
                        (pkg.label || pkg.config_id) + legacy
                    );
                    added += 1;
                });
            } else {
                console.error('Failed to load config packages:', response.status);
            }
        } catch (error) {
            console.error('Error loading config packages:', error);
        }

        if (added === 0) {
            try {
                const response = await fetch('/api/config/directories', { credentials: 'same-origin' });
                if (response.ok) {
                    const data = await response.json();
                    (data.directories || []).forEach(function (dir) {
                        if (excludeConfigId && dir === excludeConfigId) return;
                        appendRunnerSourceOption(selectEl, dir, dir);
                        added += 1;
                    });
                }
            } catch (error) {
                console.error('Error loading config directories:', error);
            }
        }

        if (added === 0) {
            const hint = document.createElement('option');
            hint.value = '';
            hint.disabled = true;
            hint.textContent = '(No packages with runner files — check runflow/config)';
            selectEl.appendChild(hint);
        }
        return added;
    }

    async function loadConfigDirectories() {
        const select = document.getElementById('baseline-config-dir');
        if (!select) return;
        const onRaceConfig = isRaceConfigurationPage() && getTargetConfigId();
        const placeholder = onRaceConfig
            ? 'Select a package with runner files…'
            : 'Use /data directory (default)';
        await loadPackagesWithRunners(select, getTargetConfigId(), placeholder);
    }

    async function loadRunnerFilesFromDataDirectory() {
        try {
            const response = await fetch('/api/data/files?extension=csv', { credentials: 'same-origin' });
            if (!response.ok) return;
            const data = await response.json();
            const runnerFiles = (data.files || []).filter(function (f) {
                return f.endsWith('_runners.csv');
            });
            const summary = document.getElementById('baseline-source-summary');
            if (summary) summary.textContent = 'Using runner files from /data directory.';
            setStep1Visible(runnerFiles.length > 0);
            renderBaselineFileSelection(runnerFiles);
            updateBaselineCalculateButton();
            clearBaselineErrors();
        } catch (error) {
            console.error('Error loading data runner files:', error);
        }
    }

    // Load runner files from the active source package
    async function loadRunnerFilesForBaseline() {
        const sourceId = getRunnerSourceId();
        if (!sourceId) {
            setStep1Visible(false);
            return;
        }

        const targetId = getTargetConfigId();
        const fromOwnPackage = !!(targetId && sourceId === targetId);

        try {
            const runnerFiles = await fetchPackageRunnerFiles(sourceId);
            setStep1Visible(true);
            updateSourceSummary(sourceId, fromOwnPackage);
            renderBaselineFileSelection(runnerFiles);
            updateBaselineCalculateButton();
            clearBaselineErrors();
        } catch (error) {
            console.error('Error loading runner files:', error);
        }
    }

    async function initializeRunnerSource() {
        const targetId = getTargetConfigId();

        if (targetId) {
            const packageFiles = await fetchPackageRunnerFiles(targetId);
            if (packageFiles.length > 0) {
                baselineState.runnerSourceId = targetId;
                setEmptyPackageHintVisible(false);
                setSourcePickerVisible(false);
                setChangeSourceLinkVisible(true);
                const select = document.getElementById('baseline-config-dir');
                if (select) select.value = '';
                setStep1Visible(true);
                updateSourceSummary(targetId, true);
                renderBaselineFileSelection(packageFiles);
                updateBaselineCalculateButton();
                return;
            }
            baselineState.runnerSourceId = null;
            setEmptyPackageHintVisible(true);
            setSourcePickerVisible(true);
            setChangeSourceLinkVisible(false);
            setStep1Visible(false);
            await loadConfigDirectories();
            return;
        }

        setEmptyPackageHintVisible(false);
        setChangeSourceLinkVisible(false);
        setSourcePickerVisible(true);
        setStep1Visible(false);
        await loadConfigDirectories();
        await loadRunnerFilesFromDataDirectory();
    }

    function showAlternateSourcePicker() {
        baselineState.runnerSourceId = null;
        const select = document.getElementById('baseline-config-dir');
        if (select) select.value = '';
        setChangeSourceLinkVisible(false);
        setSourcePickerVisible(true);
        setStep1Visible(false);
        resetBaselineState();
        loadConfigDirectories();
    }

    function handleConfigDirChange() {
        const select = document.getElementById('baseline-config-dir');
        baselineState.runnerSourceId = select && select.value ? select.value.trim() : null;
        baselineState.configDir = null;
        resetBaselineState();
        if (baselineState.runnerSourceId) {
            setSourcePickerVisible(true);
            loadRunnerFilesForBaseline();
        } else if (!getTargetConfigId()) {
            loadRunnerFilesFromDataDirectory();
        } else {
            setStep1Visible(false);
        }
    }

    // Render file selection checkboxes (only when step1 is visible)
    function renderBaselineFileSelection(files) {
        const container = document.getElementById('baseline-file-selection');
        if (!container) return;
        container.innerHTML = '';

        if (files.length === 0) {
            container.innerHTML =
                '<p style="color:#7f8c8d;margin:0;">No <code>*_runners.csv</code> files in the selected package.</p>';
            updateBaselineCalculateButton();
            return;
        }
        
        files.forEach(file => {
            const label = document.createElement('label');
            label.style.cssText = 'display: flex; align-items: center; gap: 0.5rem; cursor: pointer;';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = file;
            checkbox.addEventListener('change', updateBaselineCalculateButton);
            
            const span = document.createElement('span');
            span.textContent = file;
            
            label.appendChild(checkbox);
            label.appendChild(span);
            container.appendChild(label);
        });
    }
    
    // Update Calculate Baseline button state
    function updateBaselineCalculateButton() {
        const checkboxes = document.querySelectorAll('#baseline-file-selection input[type="checkbox"]');
        const checked = Array.from(checkboxes).filter(cb => cb.checked);
        const btn = document.getElementById('baseline-calculate-btn');
        if (btn) {
            btn.disabled = checked.length === 0;
        }
    }
    
    // Calculate baseline metrics
    async function calculateBaseline() {
        const checkboxes = document.querySelectorAll('#baseline-file-selection input[type="checkbox"]');
        const selectedFiles = Array.from(checkboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);
        
        if (selectedFiles.length === 0) {
            showBaselineError('Please select at least one runner file');
            return;
        }
        
        const btn = document.getElementById('baseline-calculate-btn');
        btn.disabled = true;
        btn.textContent = 'Calculating...';
        clearBaselineErrors();
        
        try {
            const payload = baselineApiPayload({ selected_files: selectedFiles });
            
            const response = await fetch('/api/baseline/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to calculate baseline');
            }
            
            // Store baseline state (no runId yet - created in Step 3)
            baselineState.baselineMetrics = data.baseline_metrics;
            baselineState.selectedFiles = selectedFiles;
            baselineState.dataDir = data.data_dir || 'data';
            baselineState.runnerSourceId = getRunnerSourceId();
            baselineState.targetConfigId = getTargetConfigId();
            baselineState.reportsPath = data.reports_path || 'runflow';
            
            // Render baseline metrics table
            renderBaselineMetricsTable(data.baseline_metrics);
            
            // Show step 2 and 3
            document.getElementById('baseline-step2').style.display = 'block';
            document.getElementById('baseline-step3').style.display = 'block';
            
            // Render control variables table
            renderControlVariablesTable(data.baseline_metrics);
            
            // Show reference section (already rendered on page load)
            document.getElementById('control-variables-reference').style.display = 'block';
            
        } catch (error) {
            showBaselineError(error.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Calculate Baseline';
        }
    }
    
    // Render baseline metrics table
    function renderBaselineMetricsTable(metrics) {
        const container = document.getElementById('baseline-metrics-table');
        if (!container) return;
        const events = Object.keys(metrics);
        
        if (events.length === 0) {
            container.innerHTML = '<p>No baseline metrics available</p>';
            return;
        }
        
        let html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 1rem;"><thead><tr>';
        html += '<th style="padding: 0.5rem; border: 1px solid #ddd; background: #f8f9fa; text-align: left;">Metric</th>';
        events.forEach(event => {
            html += `<th style="padding: 0.5rem; border: 1px solid #ddd; background: #f8f9fa; text-align: center;">${event}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        // Participants
        html += '<tr><td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">Participants</td>';
        events.forEach(event => {
            html += `<td style="padding: 0.5rem; border: 1px solid #ddd; text-align: center;">${metrics[event].base_participants}</td>`;
        });
        html += '</tr>';
        
        // Percentiles
        const percentiles = ['P00 (Lead)', 'P05', 'P25', 'P50 (Median)', 'P75', 'P95', 'P100 (Last)'];
        const percentileKeys = ['base_p00', 'base_p05', 'base_p25', 'base_p50', 'base_p75', 'base_p95', 'base_p100'];
        
        percentiles.forEach((label, idx) => {
            html += `<tr><td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">${label}</td>`;
            events.forEach(event => {
                const value = metrics[event][percentileKeys[idx]];
                html += `<td style="padding: 0.5rem; border: 1px solid #ddd; text-align: center;">${value.toFixed(2)}</td>`;
            });
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }
    
    // Render control variables input table
    function renderControlVariablesTable(metrics) {
        const container = document.getElementById('baseline-control-variables-table');
        if (!container) return;
        const events = Object.keys(metrics);
        
        if (events.length === 0) {
            container.innerHTML = '<p>No events available</p>';
            return;
        }
        
        let html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 1rem;"><thead><tr>';
        html += '<th style="padding: 0.5rem; border: 1px solid #ddd; background: #f8f9fa; text-align: left;">Variable</th>';
        events.forEach(event => {
            html += `<th style="padding: 0.5rem; border: 1px solid #ddd; background: #f8f9fa; text-align: center;">${event}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        // Participants change
        html += '<tr><td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">Participants %</td>';
        events.forEach(event => {
            html += `<td style="padding: 0.5rem; border: 1px solid #ddd;">
                <input type="text" id="chg_participants_${event}" value="0" 
                       placeholder="40" 
                       style="width: 100%; padding: 0.25rem; border: 1px solid #ddd; border-radius: 4px;">
            </td>`;
        });
        html += '</tr>';
        
        // Percentile changes
        const percentileLabels = ['P00 (Lead) %', 'P05 %', 'P25 %', 'P50 (Median) %', 'P75 %', 'P95 %', 'P100 (Last) %'];
        const percentileKeys = ['chg_p00', 'chg_p05', 'chg_p25', 'chg_p50', 'chg_p75', 'chg_p95', 'chg_p100'];
        
        percentileLabels.forEach((label, idx) => {
            html += `<tr><td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">${label}</td>`;
            events.forEach(event => {
                html += `<td style="padding: 0.5rem; border: 1px solid #ddd;">
                    <input type="text" id="${percentileKeys[idx]}_${event}" value="0" 
                           placeholder="0.5" 
                           style="width: 100%; padding: 0.25rem; border: 1px solid #ddd; border-radius: 4px;">
                </td>`;
            });
            html += '</tr>';
        });
        
        // Cut-off time (optional)
        html += '<tr><td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">Cut-off (hh:mm)</td>';
        events.forEach(event => {
            html += `<td style="padding: 0.5rem; border: 1px solid #ddd;">
                <input type="text" id="cutoff_${event}" placeholder="06:00" pattern="^([0-1][0-9]|2[0-3]):[0-5][0-9]$"
                       style="width: 100%; padding: 0.25rem; border: 1px solid #ddd; border-radius: 4px;">
            </td>`;
        });
        html += '</tr>';
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }
    
    // Render Control Variables Reference table
    function renderControlVariablesReference() {
        const container = document.getElementById('baseline-reference-table');
        if (!container) return;
        
        let html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 1rem;">';
        html += '<thead><tr>';
        html += '<th style="padding: 0.5rem; border: 1px solid #ddd; background: #f8f9fa; text-align: left; width: 20%;">Variable</th>';
        html += '<th style="padding: 0.5rem; border: 1px solid #ddd; background: #f8f9fa; text-align: left; width: 35%;">Definition</th>';
        html += '<th style="padding: 0.5rem; border: 1px solid #ddd; background: #f8f9fa; text-align: left; width: 45%;">Allowed Range</th>';
        html += '</tr></thead><tbody>';
        
        // Participants %
        html += '<tr>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">Participants %</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'The percentage change in the number of participants from the baseline. Enter values as percentages (e.g., 40 for +40%, -20 for -20%).';
        html += '</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'The allowed range is -50% to +200%, meaning any event can have a 50% reduction in participants from baseline, and a 200% increase.';
        html += '</td>';
        html += '</tr>';
        
        // P00 (Lead)
        html += '<tr>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">P00 (Lead) %</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'The percentage change in pace for the fastest runner (lead runner).';
        html += '</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'A negative percentage means faster (lower pace), and a positive number means slower (higher pace). The allowed range is -50% to +200%.';
        html += '</td>';
        html += '</tr>';
        
        // P05
        html += '<tr>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">P05 %</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'The percentage change in pace at the front 5% point.';
        html += '</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'A negative percentage means faster (lower pace), and a positive number means slower (higher pace). The allowed range is -50% to +200%.';
        html += '</td>';
        html += '</tr>';
        
        // P25
        html += '<tr>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">P25 %</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'The percentage change in pace at the 25% point (1 in 4 runners are faster).';
        html += '</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'A negative percentage means faster (lower pace), and a positive number means slower (higher pace). The allowed range is -50% to +200%.';
        html += '</td>';
        html += '</tr>';
        
        // P50 (Median)
        html += '<tr>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">P50 (Median) %</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'The percentage change in pace for the middle runner (half faster, half slower).';
        html += '</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'A negative percentage means faster (lower pace), and a positive number means slower (higher pace). The allowed range is -50% to +200%.';
        html += '</td>';
        html += '</tr>';
        
        // P75
        html += '<tr>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">P75 %</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'The percentage change in pace at the 75% point (3 in 4 runners are faster).';
        html += '</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'A negative percentage means faster (lower pace), and a positive number means slower (higher pace). The allowed range is -50% to +200%.';
        html += '</td>';
        html += '</tr>';
        
        // P95
        html += '<tr>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">P95 %</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'The percentage change in pace near the back (95% of runners are faster).';
        html += '</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'A negative percentage means faster (lower pace), and a positive number means slower (higher pace). The allowed range is -50% to +200%.';
        html += '</td>';
        html += '</tr>';
        
        // P100 (Last)
        html += '<tr>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">P100 (Last) %</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'The percentage change in pace for the slowest runner (last runner).';
        html += '</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'A negative percentage means faster (lower pace), and a positive number means slower (higher pace). The allowed range is -50% to +200%.';
        html += '</td>';
        html += '</tr>';
        
        // Cut-off
        html += '<tr>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">Cut-off (hh:mm)</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'Optional per-event cut-off duration in hours:minutes format (e.g., "06:00" for 6 hours). The system validates that the slowest runner\'s finish time does not exceed this cut-off before generating files. If validation fails, file generation is blocked with a clear error message.';
        html += '</td>';
        html += '<td style="padding: 0.5rem; border: 1px solid #ddd;">';
        html += 'Optional';
        html += '</td>';
        html += '</tr>';
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }
    
    // Parse and convert percentage input to decimal
    // Accepts: "40", "40%", "0.5", "0.5%", "-0.5", "-0.5%"
    // Returns: decimal fraction (40 → 0.40, 0.5 → 0.005)
    function parsePercentToDecimal(inputValue) {
        if (!inputValue || inputValue.trim() === '') {
            return 0;
        }
        
        // Trim whitespace and remove optional trailing "%"
        let cleaned = inputValue.trim().replace(/%$/, '');
        
        // Parse as float
        const percentValue = parseFloat(cleaned);
        
        if (isNaN(percentValue)) {
            throw new Error(`Invalid percentage value: "${inputValue}"`);
        }
        
        // Convert percent to decimal: 40 → 0.40, 0.5 → 0.005
        return percentValue / 100;
    }
    
    // Validate percentage input in percent units (-50 to +200)
    function validatePercentRange(percentValue, fieldName) {
        if (percentValue < -50 || percentValue > 200) {
            throw new Error(
                `${fieldName} must be between -50% and +200% (entered: ${percentValue}%)`
            );
        }
    }
    
    // Calculate new baseline
    async function calculateNewBaseline() {
        if (!baselineState.baselineMetrics || !baselineState.selectedFiles) {
            showBaselineError('Please calculate baseline first');
            return;
        }
        
        const events = Object.keys(baselineState.baselineMetrics);
        const controlVariables = {};
        
        try {
            // Collect control variables from inputs and convert percent to decimal
            events.forEach(event => {
                // Parse participants %
                const participantsInput = document.getElementById(`chg_participants_${event}`).value;
                const participantsPercent = parseFloat(participantsInput.trim().replace(/%$/, '')) || 0;
                validatePercentRange(participantsPercent, `Participants % for '${event}'`);
                const chg_participants = parsePercentToDecimal(participantsInput);
                
                // Parse percentile changes
                const percentileKeys = ['chg_p00', 'chg_p05', 'chg_p25', 'chg_p50', 'chg_p75', 'chg_p95', 'chg_p100'];
                const percentileLabels = ['P00 %', 'P05 %', 'P25 %', 'P50 %', 'P75 %', 'P95 %', 'P100 %'];
                const percentileValues = {};
                
                percentileKeys.forEach((key, idx) => {
                    const input = document.getElementById(`${key}_${event}`).value;
                    const percentValue = parseFloat(input.trim().replace(/%$/, '')) || 0;
                    validatePercentRange(percentValue, `${percentileLabels[idx]} for '${event}'`);
                    percentileValues[key] = parsePercentToDecimal(input);
                });
                
                controlVariables[event] = {
                    chg_participants: chg_participants,
                    chg_p00: percentileValues.chg_p00,
                    chg_p05: percentileValues.chg_p05,
                    chg_p25: percentileValues.chg_p25,
                    chg_p50: percentileValues.chg_p50,
                    chg_p75: percentileValues.chg_p75,
                    chg_p95: percentileValues.chg_p95,
                    chg_p100: percentileValues.chg_p100
                };
                
                // Optional cut-off time
                const cutoffInput = document.getElementById(`cutoff_${event}`);
                if (cutoffInput && cutoffInput.value.trim()) {
                    controlVariables[event].cutoff_mins = cutoffInput.value.trim();
                }
            });
        } catch (validationError) {
            showBaselineControlError(validationError.message);
            return;
        }
        
        const btn = document.getElementById('baseline-calculate-new-btn');
        btn.disabled = true;
        btn.textContent = 'Calculating...';
        // Clear only control variables errors (not file selection errors)
        const controlErrorEl = document.getElementById('baseline-control-variables-error');
        if (controlErrorEl) {
            controlErrorEl.style.display = 'none';
        }
        
        try {
            const response = await fetch('/api/baseline/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(baselineApiPayload({
                    baseline_metrics: baselineState.baselineMetrics,
                    selected_files: baselineState.selectedFiles,
                    control_variables: controlVariables
                }))
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to generate new baseline');
            }
            
            // Store control variables and new baseline metrics (no runId yet - created in Step 4)
            baselineState.controlVariables = controlVariables;
            baselineState.newBaselineMetrics = data.new_baseline_metrics;
            baselineState.targetConfigId = getTargetConfigId();
            
            // Render new baseline metrics table
            renderNewBaselineMetricsTable(data.new_baseline_metrics);
            
            // Show step 4
            document.getElementById('baseline-step4').style.display = 'block';
            
        } catch (error) {
            // Handle API errors - convert backend decimal error messages to percent if needed
            let errorMessage = error.message;
            
            // Convert backend validation errors from decimal to percent format
            errorMessage = errorMessage.replace(
                /out of range \((-?\d+\.?\d*) to (\+?\d+\.?\d*)\)/g,
                (match, min, max) => {
                    const minPercent = (parseFloat(min) * 100).toFixed(0);
                    const maxPercent = (parseFloat(max) * 100).toFixed(0);
                    return `out of range (${minPercent}% to ${maxPercent}%)`;
                }
            );
            
            showBaselineControlError(errorMessage);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Calculate New Baseline';
        }
    }
    
    // Render new baseline metrics table
    function renderNewBaselineMetricsTable(newMetrics) {
        const container = document.getElementById('baseline-new-metrics-table');
        if (!container) return;
        const events = Object.keys(newMetrics);
        
        if (events.length === 0) {
            container.innerHTML = '<p>No new baseline metrics available</p>';
            return;
        }
        
        let html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 1rem;"><thead><tr>';
        html += '<th style="padding: 0.5rem; border: 1px solid #ddd; background: #f8f9fa; text-align: left;">Metric</th>';
        events.forEach(event => {
            html += `<th style="padding: 0.5rem; border: 1px solid #ddd; background: #f8f9fa; text-align: center;">${event}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        // Participants
        html += '<tr><td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">Participants (new)</td>';
        events.forEach(event => {
            html += `<td style="padding: 0.5rem; border: 1px solid #ddd; text-align: center;">${newMetrics[event].new_participants}</td>`;
        });
        html += '</tr>';
        
        // Percentiles
        const percentiles = ['P00 (Lead)', 'P05', 'P25', 'P50 (Median)', 'P75', 'P95', 'P100 (Last)'];
        const percentileKeys = ['new_p00', 'new_p05', 'new_p25', 'new_p50', 'new_p75', 'new_p95', 'new_p100'];
        
        percentiles.forEach((label, idx) => {
            html += `<tr><td style="padding: 0.5rem; border: 1px solid #ddd; font-weight: 600;">${label}</td>`;
            events.forEach(event => {
                const value = newMetrics[event][percentileKeys[idx]];
                html += `<td style="padding: 0.5rem; border: 1px solid #ddd; text-align: center;">${value.toFixed(2)}</td>`;
            });
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }
    
    // Create new files
    async function createNewFiles() {
        if (!baselineState.baselineMetrics || !baselineState.controlVariables || !baselineState.newBaselineMetrics) {
            showBaselineError('Please calculate baseline and new baseline first');
            return;
        }
        
        // Get file name suffix (optional)
        const suffixInput = document.getElementById('baseline-file-suffix');
        const fileSuffix = suffixInput ? suffixInput.value.trim() : '';
        
        // Validate suffix format (alphanumeric, underscore, hyphen only)
        if (fileSuffix && !/^[a-zA-Z0-9_-]+$/.test(fileSuffix)) {
            showBaselineError('File name suffix can only contain letters, numbers, underscores, and hyphens');
            return;
        }
        
        const btn = document.getElementById('baseline-create-files-btn');
        btn.disabled = true;
        btn.textContent = 'Creating Files...';
        
        try {
            const response = await fetch('/api/baseline/create-files', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(createFilesPayload({
                    baseline_metrics: baselineState.baselineMetrics,
                    selected_files: baselineState.selectedFiles,
                    control_variables: baselineState.controlVariables,
                    file_suffix: fileSuffix || null
                }))
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to create files');
            }
            
            // Store runId (created in Step 4)
            baselineState.runId = data.run_id;
            
            // Get reports_path from stored state
            const reportsPath = baselineState.reportsPath || 'runflow';

            let filePath = data.target_config_id
                ? `runflow/config/${data.target_config_id}`
                : `${reportsPath}/baseline/${baselineState.runId}`;
            if (data.generated_files && data.generated_files.length) {
                const names = data.generated_files.map(function (f) { return f.filename; }).join(', ');
                filePath += ' — ' + names;
            }
            const pathElement = document.getElementById('baseline-file-path');
            const downloadLink = document.getElementById('baseline-download-link');
            const successMessage = document.getElementById('baseline-success-message');
            
            if (pathElement) {
                pathElement.textContent = filePath;
            }
            
            if (downloadLink) {
                downloadLink.href = `/api/baseline/download?run_id=${baselineState.runId}`;
            }
            
            if (successMessage) {
                successMessage.style.display = 'block';
                successMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        } catch (error) {
            showBaselineError(error.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Create New Files';
        }
    }
    
    function resetBaselineState() {
        const targetConfigId = getTargetConfigId();
        const runnerSourceId = getRunnerSourceId();
        baselineState = {
            runId: null,
            baselineMetrics: null,
            selectedFiles: [],
            dataDir: null,
            configDir: null,
            targetConfigId: targetConfigId,
            runnerSourceId: runnerSourceId,
            controlVariables: null,
            newBaselineMetrics: null,
            reportsPath: null
        };
        
        // Reset UI
        document.getElementById('baseline-step2').style.display = 'none';
        document.getElementById('baseline-step3').style.display = 'none';
        document.getElementById('baseline-step4').style.display = 'none';
        
        // Hide success message
        const successMessage = document.getElementById('baseline-success-message');
        if (successMessage) {
            successMessage.style.display = 'none';
        }
        
        // Clear file suffix input
        const suffixInput = document.getElementById('baseline-file-suffix');
        if (suffixInput) {
            suffixInput.value = '';
        }
        
        // Uncheck all checkboxes
        document.querySelectorAll('#baseline-file-selection input[type="checkbox"]').forEach(cb => {
            cb.checked = false;
        });
        
        updateBaselineCalculateButton();
        clearBaselineErrors();
    }

    // Clear baseline state
    function clearBaseline() {
        resetBaselineState();
    }
    
    // Show baseline error (for file selection)
    function showBaselineError(message) {
        const errorEl = document.getElementById('baseline-file-selection-error');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.style.display = 'block';
        }
    }
    
    // Show baseline control variables error (for Calculate New Baseline)
    function showBaselineControlError(message) {
        const errorEl = document.getElementById('baseline-control-variables-error');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.style.display = 'block';
            // Scroll to error
            errorEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
    
    // Show baseline success (deprecated - now using inline success message)
    function showBaselineSuccess(message) {
        // This function is kept for backward compatibility but is no longer used
        // Success messages are now shown inline below the Create New Files button
    }
    
    // Clear baseline errors
    function clearBaselineErrors() {
        const fileErrorEl = document.getElementById('baseline-file-selection-error');
        if (fileErrorEl) {
            fileErrorEl.style.display = 'none';
        }
        const controlErrorEl = document.getElementById('baseline-control-variables-error');
        if (controlErrorEl) {
            controlErrorEl.style.display = 'none';
        }
    }

    let initRunnersBaselinePromise = null;

    async function initRunnersBaselineImpl() {
        if (!listenersBound) {
            const calcBtn = document.getElementById('baseline-calculate-btn');
            const calcNewBtn = document.getElementById('baseline-calculate-new-btn');
            const createBtn = document.getElementById('baseline-create-files-btn');
            const clearBtn = document.getElementById('baseline-clear-btn');
            const configSelect = document.getElementById('baseline-config-dir');
            if (calcBtn) calcBtn.addEventListener('click', calculateBaseline);
            if (calcNewBtn) calcNewBtn.addEventListener('click', calculateNewBaseline);
            if (createBtn) createBtn.addEventListener('click', createNewFiles);
            if (clearBtn) clearBtn.addEventListener('click', clearBaseline);
            if (configSelect) configSelect.addEventListener('change', handleConfigDirChange);
            const changeSourceBtn = document.getElementById('baseline-change-source-btn');
            if (changeSourceBtn) {
                changeSourceBtn.addEventListener('click', showAlternateSourcePicker);
            }
            listenersBound = true;
        }

        const urlConfigId = getConfigIdFromUrl();
        if (urlConfigId) {
            baselineState.targetConfigId = urlConfigId;
        }

        await initializeRunnerSource();

        renderControlVariablesReference();
    }

    window.initRunnersBaseline = function initRunnersBaseline() {
        if (!initRunnersBaselinePromise) {
            initRunnersBaselinePromise = initRunnersBaselineImpl().finally(function () {
                initRunnersBaselinePromise = null;
            });
        }
        return initRunnersBaselinePromise;
    };

    document.addEventListener('DOMContentLoaded', function() {
        if (!document.getElementById('baseline-file-selection')) return;
        const workspace = document.getElementById('race-config-workspace');
        if (workspace) {
            const tab = new URLSearchParams(window.location.search).get('tab');
            if (tab === 'runners') {
                window.initRunnersBaseline();
            }
            return;
        }
        window.initRunnersBaseline();
    });
})();
