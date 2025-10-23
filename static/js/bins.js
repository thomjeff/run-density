/**
 * Bin-Level Details Table with sorting, filtering, and pagination
 * Handles both local and cloud environments
 * 
 * @file bins.js
 * @description Interactive table for bin-level density and flow metrics
 */

// Configuration
const BINS_PER_PAGE = 50;
const MAX_DISPLAY_PAGES = 5;

// State management
let allBinsData = [];
let filteredBinsData = [];
let currentPage = 1;
let currentSort = { column: null, direction: 'asc' };

// DOM elements
let binsTableBody;
let paginationInfo;
let prevButton;
let nextButton;
let pageNumbers;
let segmentFilter;
let losFilter;
let clearFiltersButton;
let totalBinsCount;

/**
 * Initialize the bins table
 */
function initBinsTable() {
    console.log('Initializing bins table...');
    
    // Get DOM elements
    binsTableBody = document.getElementById('bins-table-body');
    paginationInfo = document.getElementById('pagination-info');
    prevButton = document.getElementById('prev-page');
    nextButton = document.getElementById('next-page');
    pageNumbers = document.getElementById('page-numbers');
    segmentFilter = document.getElementById('segment-filter');
    losFilter = document.getElementById('los-filter');
    clearFiltersButton = document.getElementById('clear-filters');
    totalBinsCount = document.getElementById('total-bins-count');
    
    // Set up event listeners
    setupEventListeners();
    
    // Load data
    loadBinsData();
}

/**
 * Set up event listeners for table interactions
 */
function setupEventListeners() {
    // Pagination buttons
    if (prevButton) {
        prevButton.addEventListener('click', () => changePage(currentPage - 1));
    }
    if (nextButton) {
        nextButton.addEventListener('click', () => changePage(currentPage + 1));
    }
    
    // Filter inputs
    if (segmentFilter) {
        segmentFilter.addEventListener('input', debounce(applyFilters, 300));
    }
    if (losFilter) {
        losFilter.addEventListener('change', applyFilters);
    }
    if (clearFiltersButton) {
        clearFiltersButton.addEventListener('click', clearFilters);
    }
    
    // Table header sorting
    const sortableHeaders = document.querySelectorAll('#bins-table th.sortable');
    sortableHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const column = header.dataset.sort;
            sortTable(column);
        });
    });
}

/**
 * Load bins data from API
 */
async function loadBinsData() {
    try {
        showLoadingState();
        
        const response = await fetch('/api/bins');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.bins && data.bins.length > 0) {
            allBinsData = data.bins;
            filteredBinsData = [...allBinsData];
            
            // Update total count display
            if (totalBinsCount) {
                totalBinsCount.textContent = `${data.total_count.toLocaleString()} bins available`;
            }
            
            console.log(`Loaded ${allBinsData.length} bin records`);
            renderTable();
        } else {
            showEmptyState();
        }
        
    } catch (error) {
        console.error('Failed to load bins data:', error);
        showErrorState(error.message);
    }
}

/**
 * Show loading state
 */
function showLoadingState() {
    document.getElementById('bins-loading').style.display = 'block';
    document.getElementById('bins-empty').style.display = 'none';
    document.getElementById('bins-content').style.display = 'none';
}

/**
 * Show empty state
 */
function showEmptyState() {
    document.getElementById('bins-loading').style.display = 'none';
    document.getElementById('bins-empty').style.display = 'block';
    document.getElementById('bins-content').style.display = 'none';
}

/**
 * Show error state
 */
function showErrorState(message) {
    document.getElementById('bins-loading').style.display = 'none';
    document.getElementById('bins-empty').style.display = 'block';
    document.getElementById('bins-content').style.display = 'none';
    
    const emptyDiv = document.getElementById('bins-empty');
    emptyDiv.innerHTML = `
        <h3>Error Loading Data</h3>
        <p>Failed to load bin data: ${message}</p>
        <button onclick="loadBinsData()" style="margin-top: 1rem; padding: 0.5rem 1rem; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">
            Retry
        </button>
    `;
}

/**
 * Render the table with current data
 */
function renderTable() {
    document.getElementById('bins-loading').style.display = 'none';
    document.getElementById('bins-empty').style.display = 'none';
    document.getElementById('bins-content').style.display = 'block';
    
    // Calculate pagination
    const totalPages = Math.ceil(filteredBinsData.length / BINS_PER_PAGE);
    const startIndex = (currentPage - 1) * BINS_PER_PAGE;
    const endIndex = Math.min(startIndex + BINS_PER_PAGE, filteredBinsData.length);
    const pageData = filteredBinsData.slice(startIndex, endIndex);
    
    // Render table rows
    binsTableBody.innerHTML = '';
    pageData.forEach((bin, index) => {
        const row = createTableRow(bin, startIndex + index);
        binsTableBody.appendChild(row);
    });
    
    // Update pagination
    updatePagination(totalPages, startIndex, endIndex);
}

/**
 * Create a table row for a bin record
 */
function createTableRow(bin, rowIndex) {
    const row = document.createElement('tr');
    row.dataset.index = rowIndex;
    
    // Add click handler for future map integration
    row.addEventListener('click', () => {
        // Remove existing selection
        document.querySelectorAll('#bins-table tbody tr.selected').forEach(r => {
            r.classList.remove('selected');
        });
        
        // Add selection to current row
        row.classList.add('selected');
        
        console.log(`Selected bin: ${bin.segment_id} (${bin.start_km}-${bin.end_km}km)`);
    });
    
    row.innerHTML = `
        <td>${bin.segment_id}</td>
        <td class="text-right">${bin.start_km.toFixed(2)}</td>
        <td class="text-right">${bin.end_km.toFixed(2)}</td>
        <td>${bin.t_start}</td>
        <td>${bin.t_end}</td>
        <td class="text-right">${bin.density.toFixed(2)}</td>
        <td class="text-right">${bin.rate.toFixed(2)}</td>
        <td class="text-center">
            <span class="badge-los badge-${bin.los_class}">${bin.los_class}</span>
        </td>
    `;
    
    return row;
}

/**
 * Update pagination controls
 */
function updatePagination(totalPages, startIndex, endIndex) {
    // Update pagination info
    if (paginationInfo) {
        paginationInfo.textContent = `Showing ${startIndex + 1}-${endIndex} of ${filteredBinsData.length.toLocaleString()} bins`;
    }
    
    // Update buttons
    if (prevButton) {
        prevButton.disabled = currentPage <= 1;
    }
    if (nextButton) {
        nextButton.disabled = currentPage >= totalPages;
    }
    
    // Update page numbers
    if (pageNumbers) {
        pageNumbers.innerHTML = '';
        
        const startPage = Math.max(1, currentPage - Math.floor(MAX_DISPLAY_PAGES / 2));
        const endPage = Math.min(totalPages, startPage + MAX_DISPLAY_PAGES - 1);
        
        for (let i = startPage; i <= endPage; i++) {
            const button = document.createElement('button');
            button.textContent = i;
            button.className = i === currentPage ? 'active' : '';
            button.addEventListener('click', () => changePage(i));
            pageNumbers.appendChild(button);
        }
    }
}

/**
 * Change to a specific page
 */
function changePage(page) {
    const totalPages = Math.ceil(filteredBinsData.length / BINS_PER_PAGE);
    if (page >= 1 && page <= totalPages) {
        currentPage = page;
        renderTable();
    }
}

/**
 * Sort the table by a column
 */
function sortTable(column) {
    if (currentSort.column === column) {
        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        currentSort.column = column;
        currentSort.direction = 'asc';
    }
    
    // Update header classes
    document.querySelectorAll('#bins-table th.sortable').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
        if (th.dataset.sort === column) {
            th.classList.add(`sort-${currentSort.direction}`);
        }
    });
    
    // Sort the data
    filteredBinsData.sort((a, b) => {
        let aVal = a[column];
        let bVal = b[column];
        
        // Handle numeric columns
        if (['start_km', 'end_km', 'density', 'rate'].includes(column)) {
            aVal = parseFloat(aVal) || 0;
            bVal = parseFloat(bVal) || 0;
        }
        
        // Handle string columns
        if (typeof aVal === 'string') {
            aVal = aVal.toLowerCase();
            bVal = bVal.toLowerCase();
        }
        
        if (currentSort.direction === 'asc') {
            return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
        } else {
            return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
        }
    });
    
    // Reset to first page and re-render
    currentPage = 1;
    renderTable();
}

/**
 * Apply filters to the data
 */
function applyFilters() {
    const segmentValue = segmentFilter ? segmentFilter.value.toLowerCase().trim() : '';
    const losValue = losFilter ? losFilter.value : '';
    
    filteredBinsData = allBinsData.filter(bin => {
        const segmentMatch = !segmentValue || bin.segment_id.toLowerCase().includes(segmentValue);
        const losMatch = !losValue || bin.los_class === losValue;
        
        return segmentMatch && losMatch;
    });
    
    // Reset to first page and re-render
    currentPage = 1;
    renderTable();
    
    console.log(`Applied filters: ${filteredBinsData.length} bins match criteria`);
}

/**
 * Clear all filters
 */
function clearFilters() {
    if (segmentFilter) segmentFilter.value = '';
    if (losFilter) losFilter.value = '';
    
    filteredBinsData = [...allBinsData];
    currentPage = 1;
    renderTable();
    
    console.log('Cleared all filters');
}

/**
 * Debounce function to limit API calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initBinsTable);
