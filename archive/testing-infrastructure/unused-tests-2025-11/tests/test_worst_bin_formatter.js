/**
 * Unit tests for formatWorstBinLabel (Issue #286)
 * 
 * Run with: node tests/test_worst_bin_formatter.js
 */

// Copy of the formatter function from density.html
function formatWorstBinLabel(bin) {
    if (!bin || typeof bin !== 'object') {
        return '—';
    }
    
    // Helper: Pick first available number from keys
    function pickNumber(obj, keys) {
        for (const k of keys) {
            const v = obj[k];
            if (typeof v === 'number' && !isNaN(v)) return v;
            if (typeof v === 'string' && v.trim() && !isNaN(Number(v))) return Number(v);
        }
        return null;
    }
    
    // Helper: Pick first available string from keys
    function pickString(obj, keys) {
        for (const k of keys) {
            const v = obj[k];
            if (typeof v === 'string' && v.trim()) return v.trim();
        }
        return null;
    }
    
    // Helper: Convert ISO or HH:MM to HH:MM format
    function hhmmFromISO(s) {
        if (/^\d{2}:\d{2}$/.test(s)) return s;  // Already HH:MM
        try {
            const d = new Date(s);
            if (isNaN(d.getTime())) return s;
            const hh = String(d.getHours()).padStart(2, '0');
            const mm = String(d.getMinutes()).padStart(2, '0');
            return `${hh}:${mm}`;
        } catch {
            return s;
        }
    }
    
    // Get segment ID
    const segment = pickString(bin, ['segment_id', 'seg_id', 'bin_id']) || '—';
    
    // Get distance in km (prefer km, else convert from meters)
    let dStartKm = pickNumber(bin, ['d_start_km', 'dist_start_km', 'start_km']);
    let dEndKm = pickNumber(bin, ['d_end_km', 'dist_end_km', 'end_km']);
    if (dStartKm == null && dEndKm == null) {
        const dStartM = pickNumber(bin, ['d_start_m', 'dist_start_m', 's0_m']);
        const dEndM = pickNumber(bin, ['d_end_m', 'dist_end_m', 's1_m']);
        if (dStartM != null) dStartKm = dStartM / 1000;
        if (dEndM != null) dEndKm = dEndM / 1000;
    }
    const hasDistances = dStartKm != null && dEndKm != null;
    const distLabel = hasDistances
        ? `${dStartKm.toFixed(3)}–${dEndKm.toFixed(3)} km`
        : '';
    
    // Get time window (prefer ISO, accept HH:MM)
    const tStart = pickString(bin, ['t_start', 't0', 'start_t', 'time']);
    const tEnd = pickString(bin, ['t_end', 't1', 'end_t']);
    let timeLabel = '';
    if (tStart && tEnd) {
        timeLabel = `${hhmmFromISO(tStart)}–${hhmmFromISO(tEnd)}`;
    } else if (tStart && tStart.includes('-')) {
        // Handle time already formatted as "HH:MM-HH:MM" 
        timeLabel = tStart.replace('-', '–');
    }
    
    // Compose: "Worst Bin: SEGMENT DISTANCE · TIME"
    let label = `Worst Bin: ${segment}`;
    if (distLabel) label += ` ${distLabel}`;
    if (timeLabel) label += ` · ${timeLabel}`;
    
    return label;
}

// Test suite
let passed = 0;
let failed = 0;

function assertEqual(actual, expected, testName) {
    if (actual === expected) {
        console.log(`✅ PASS: ${testName}`);
        passed++;
    } else {
        console.log(`❌ FAIL: ${testName}`);
        console.log(`   Expected: "${expected}"`);
        console.log(`   Actual:   "${actual}"`);
        failed++;
    }
}

// Test 1: Full format with km + ISO times (use local timezone-aware ISO)
const bin1 = { 
    segment_id: 'M2', 
    d_start_km: 0, 
    d_end_km: 0.2, 
    t_start: '2025-10-20T07:00:00', 
    t_end: '2025-10-20T07:02:00' 
};
assertEqual(
    formatWorstBinLabel(bin1), 
    'Worst Bin: M2 0.000–0.200 km · 07:00–07:02',
    'formats with km + ISO times'
);

// Test 2: Full format with meters + HH:MM
const bin2 = { 
    seg_id: 'A1', 
    d_start_m: 50, 
    d_end_m: 250, 
    t0: '07:10', 
    t1: '07:12' 
};
assertEqual(
    formatWorstBinLabel(bin2), 
    'Worst Bin: A1 0.050–0.250 km · 07:10–07:12',
    'formats with meters + HH:MM'
);

// Test 3: Omits missing time
const bin3 = { 
    segment_id: 'B3', 
    d_start_km: 0.4, 
    d_end_km: 0.6 
};
assertEqual(
    formatWorstBinLabel(bin3), 
    'Worst Bin: B3 0.400–0.600 km',
    'omits missing time'
);

// Test 4: Omits missing distance
const bin4 = { 
    segment_id: 'C2', 
    t_start: '08:00', 
    t_end: '08:02' 
};
assertEqual(
    formatWorstBinLabel(bin4), 
    'Worst Bin: C2 · 08:00–08:02',
    'omits missing distance'
);

// Test 5: Handles null/undefined
assertEqual(
    formatWorstBinLabel(null), 
    '—',
    'handles null input'
);

// Test 6: Handles empty object
assertEqual(
    formatWorstBinLabel({}), 
    'Worst Bin: —',
    'handles empty object'
);

// Test 7: Pre-formatted time (HH:MM-HH:MM)
const bin7 = {
    segment_id: 'D1',
    start_km: 0.0,
    end_km: 0.2,
    time: '07:42-07:44'
};
assertEqual(
    formatWorstBinLabel(bin7),
    'Worst Bin: D1 0.000–0.200 km · 07:42–07:44',
    'handles pre-formatted time with hyphen'
);

// Test 8: Uses start_km/end_km (API format)
const bin8 = {
    segment_id: 'E1',
    start_km: 1.5,
    end_km: 1.7,
    time: '09:00-09:02'
};
assertEqual(
    formatWorstBinLabel(bin8),
    'Worst Bin: E1 1.500–1.700 km · 09:00–09:02',
    'uses start_km/end_km from API'
);

// Test 9: No trailing density numeric (the bug we're fixing)
const bin9 = {
    segment_id: 'M2',
    start_km: 0.0,
    end_km: 0.2,
    time: '07:00-07:02',
    density: 0.755,  // This should NOT appear in the label
    rate: 10.19      // This should NOT appear in the label
};
const result9 = formatWorstBinLabel(bin9);
assertEqual(
    result9,
    'Worst Bin: M2 0.000–0.200 km · 07:00–07:02',
    'does not include density or rate in label'
);
// Extra check: ensure no trailing parentheses
if (result9.includes('(') || result9.includes(')')) {
    console.log(`❌ FAIL: Label should not contain parentheses`);
    console.log(`   Actual: "${result9}"`);
    failed++;
} else {
    console.log(`✅ PASS: No stray numerics in parentheses`);
    passed++;
}

// Summary
console.log('\n' + '='.repeat(50));
console.log(`Test Results: ${passed} passed, ${failed} failed`);
if (failed === 0) {
    console.log('✅ All tests passed!');
    process.exit(0);
} else {
    console.log('❌ Some tests failed');
    process.exit(1);
}

