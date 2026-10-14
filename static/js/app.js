/**
 * DGN to PDF Studio - Frontend Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const dropzoneDefault = document.getElementById('dropzoneDefault');
    const dropzoneSelected = document.getElementById('dropzoneSelected');
    const selectedFileName = document.getElementById('selectedFileName');
    const selectedFileSize = document.getElementById('selectedFileSize');
    const removeFileBtn = document.getElementById('removeFileBtn');

    const paperSizeSelect = document.getElementById('paperSizeSelect');
    const orientationSelect = document.getElementById('orientationSelect');
    const convertBtn = document.getElementById('convertBtn');
    const convertBtnText = document.getElementById('convertBtnText');
    const convertSpinner = document.getElementById('convertSpinner');

    const conversionProgress = document.getElementById('conversionProgress');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressStatusText = document.getElementById('progressStatusText');

    const viewerEmptyState = document.getElementById('viewerEmptyState');
    const viewerResultState = document.getElementById('viewerResultState');
    const resultFileName = document.getElementById('resultFileName');
    const btnDownloadPdf = document.getElementById('btnDownloadPdf');
    const btnDownloadPng = document.getElementById('btnDownloadPng');
    const btnOpenNewTab = document.getElementById('btnOpenNewTab');

    const pdfIframe = document.getElementById('pdfIframe');
    const previewImage = document.getElementById('previewImage');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    // Zoom controls
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomResetBtn = document.getElementById('zoomResetBtn');
    const zoomLevelText = document.getElementById('zoomLevelText');

    // Metadata elements
    const metaDgnVersion = document.getElementById('metaDgnVersion');
    const metaVectorCount = document.getElementById('metaVectorCount');
    const metaSizes = document.getElementById('metaSizes');
    const metaDimensions = document.getElementById('metaDimensions');
    const metaDuration = document.getElementById('metaDuration');

    // Info Modal
    const btnInfoModal = document.getElementById('btnInfoModal');
    const infoModal = document.getElementById('infoModal');
    const btnCloseModal = document.getElementById('btnCloseModal');
    const btnModalOk = document.getElementById('btnModalOk');

    // Sample chips
    const sampleChips = document.querySelectorAll('.sample-chip');

    // State
    let selectedFile = null;
    let selectedSampleId = null;
    let currentZoom = 1.0;
    let progressTimer = null;
    let isProcessing = false;

    // ==========================================================================
    // File Selection & Drag-and-Drop
    // ==========================================================================

    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (isProcessing) return;
        fileInput.click();
    });

    dropzone.addEventListener('click', () => {
        if (isProcessing) return;
        if (!selectedFile && !selectedSampleId) {
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!isProcessing) dropzone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('drag-over');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        if (isProcessing) return;
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (isProcessing) return;
        clearSelectedFile();
    });

    function handleFileSelect(file) {
        if (!file.name.toLowerCase().endsWith('.dgn')) {
            showToast('Please select a valid MicroStation .dgn file.', 'error');
            return;
        }

        selectedFile = file;
        selectedSampleId = null;
        selectedFileName.textContent = file.name;
        selectedFileSize.textContent = formatBytes(file.size);

        sampleChips.forEach(c => c.classList.remove('active-chip'));

        dropzoneDefault.classList.add('hidden');
        dropzoneSelected.classList.remove('hidden');
        convertBtnText.textContent = `Convert "${file.name}" to PDF`;

        showToast(`Loaded ${file.name} (${formatBytes(file.size)})`, 'success');
    }

    function clearSelectedFile() {
        selectedFile = null;
        selectedSampleId = null;
        fileInput.value = '';
        sampleChips.forEach(c => c.classList.remove('active-chip'));
        dropzoneSelected.classList.add('hidden');
        dropzoneDefault.classList.remove('hidden');
        convertBtnText.textContent = 'Convert DGN to PDF';
    }

    // ==========================================================================
    // Quick-Try Samples
    // ==========================================================================

    sampleChips.forEach(chip => {
        chip.addEventListener('click', () => {
            if (isProcessing) return;

            const sampleId = chip.dataset.sample;
            selectedSampleId = sampleId;
            selectedFile = null;
            fileInput.value = '';

            sampleChips.forEach(c => c.classList.remove('active-chip'));
            chip.classList.add('active-chip');

            selectedFileName.textContent = sampleId;
            selectedFileSize.textContent = chip.dataset.sampleName || 'Sample CAD File';

            dropzoneDefault.classList.add('hidden');
            dropzoneSelected.classList.remove('hidden');
            convertBtnText.textContent = `Convert "${sampleId}" to PDF`;

            showToast(`Selected sample "${sampleId}". Click Convert or adjust settings below.`, 'success');
        });
    });

    // ==========================================================================
    // Conversion Pipeline
    // ==========================================================================

    convertBtn.addEventListener('click', () => {
        if (isProcessing) return;
        if (!selectedFile && !selectedSampleId) {
            showToast('Please upload or select a DGN file first.', 'error');
            fileInput.click();
            return;
        }
        triggerConversion();
    });

    async function triggerConversion() {
        if (isProcessing) return;
        setConvertingState(true);

        const isLargeFile = (selectedFile && selectedFile.size > 10 * 1024 * 1024) || (selectedSampleId === 'House_Model.dgn');
        startProgressSimulation(isLargeFile);

        const paperSize = paperSizeSelect.value;
        const orientation = orientationSelect.value;
        const theme = document.querySelector('input[name="theme"]:checked')?.value || 'white';

        try {
            let response;
            if (selectedFile) {
                const formData = new FormData();
                formData.append('file', selectedFile);
                formData.append('paper_size', paperSize);
                formData.append('orientation', orientation);
                formData.append('theme', theme);

                response = await fetch('/api/convert', {
                    method: 'POST',
                    body: formData
                });
            } else if (selectedSampleId) {
                response = await fetch('/api/convert-sample', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sample_id: selectedSampleId,
                        paper_size: paperSize,
                        orientation: orientation,
                        theme: theme
                    })
                });
            }

            // Safe JSON parse to avoid SyntaxError
            const rawText = await response.text();
            let data;
            try {
                data = JSON.parse(rawText);
            } catch (jsonErr) {
                console.error('Non-JSON response:', rawText);
                throw new Error(`Server returned status ${response.status}. Please try again.`);
            }

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Conversion failed on server.');
            }

            finishProgressSimulation();
            displayConversionResult(data);
            showToast('Conversion completed successfully! Clean PDF generated.', 'success');
        } catch (err) {
            stopProgressSimulation();
            console.error('Conversion error:', err);
            showToast(err.message || 'Error converting DGN file.', 'error');
        } finally {
            setConvertingState(false);
        }
    }

    function setConvertingState(converting) {
        isProcessing = converting;
        convertBtn.disabled = converting;
        browseBtn.disabled = converting;
        removeFileBtn.disabled = converting;
        sampleChips.forEach(c => c.disabled = converting);

        if (converting) {
            convertSpinner.classList.remove('hidden');
            conversionProgress.classList.remove('hidden');
        } else {
            convertSpinner.classList.add('hidden');
            conversionProgress.classList.add('hidden');
        }
    }

    function startProgressSimulation(isLargeFile = false) {
        let percent = 10;
        progressBarFill.style.width = `${percent}%`;

        const steps = isLargeFile ? [
            { p: 20, msg: 'Loading 28 MB DGN model & reading coordinate units...' },
            { p: 40, msg: 'Extracting 53,000+ vector entities...' },
            { p: 65, msg: 'Rasterizing CAD geometry vectors to PDF canvas...' },
            { p: 85, msg: 'Normalizing vector streams & removing evaluation marks...' },
            { p: 95, msg: 'Finalizing clean high-precision PDF document...' }
        ] : [
            { p: 25, msg: 'Reading DGN binary headers & units...' },
            { p: 50, msg: 'Rasterizing CAD geometry vectors...' },
            { p: 75, msg: 'Normalizing PDF streams & removing evaluation marks...' },
            { p: 90, msg: 'Finalizing clean high-precision PDF document...' }
        ];

        let stepIdx = 0;
        const intervalMs = isLargeFile ? 2500 : 400;

        clearInterval(progressTimer);
        progressTimer = setInterval(() => {
            if (stepIdx < steps.length) {
                progressBarFill.style.width = `${steps[stepIdx].p}%`;
                progressStatusText.innerHTML = `<i class="fa-solid fa-microchip fa-spin"></i> <span>${steps[stepIdx].msg}</span>`;
                stepIdx++;
            }
        }, intervalMs);
    }

    function finishProgressSimulation() {
        clearInterval(progressTimer);
        progressBarFill.style.width = '100%';
        progressStatusText.innerHTML = `<i class="fa-solid fa-check"></i> <span>PDF rendering completed!</span>`;
    }

    function stopProgressSimulation() {
        clearInterval(progressTimer);
        progressBarFill.style.width = '0%';
    }

    // ==========================================================================
    // Render Results & Viewer
    // ==========================================================================

    function displayConversionResult(data) {
        const meta = data.metadata || {};

        viewerEmptyState.classList.add('hidden');
        viewerResultState.classList.remove('hidden');

        resultFileName.textContent = data.pdf_filename || 'drawing.pdf';

        // Action links
        btnDownloadPdf.href = data.download_url;
        btnDownloadPdf.download = data.pdf_filename || 'converted.pdf';

        btnDownloadPng.href = data.preview_thumb_url;
        btnDownloadPng.download = (data.pdf_filename ? data.pdf_filename.replace('.pdf', '.png') : 'preview.png');

        btnOpenNewTab.href = data.preview_pdf_url;

        // Load viewer sources
        pdfIframe.src = data.preview_pdf_url;
        previewImage.src = data.preview_thumb_url;

        // Reset image zoom
        resetZoom();

        // Populate metadata
        metaDgnVersion.textContent = meta.dgn_version || 'MicroStation DGN';
        metaVectorCount.textContent = meta.vector_elements_count !== undefined 
            ? `${meta.vector_elements_count.toLocaleString()} paths` 
            : 'Vector Core';
        
        const inSize = meta.input_size_formatted || '0 KB';
        const outSize = meta.output_size_formatted || '0 KB';
        metaSizes.textContent = `${inSize} -> ${outSize}`;

        if (meta.page_width && meta.page_height) {
            metaDimensions.textContent = `${meta.paper_size || 'Custom'} (${meta.page_width} × ${meta.page_height} pt)`;
        } else {
            metaDimensions.textContent = meta.paper_size || 'A4 Standard';
        }

        metaDuration.textContent = meta.total_time_seconds 
            ? `${meta.total_time_seconds}s` 
            : 'Fast';
    }

    // ==========================================================================
    // Tabs Controller
    // ==========================================================================

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.tab;
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            if (targetId === 'pdfView') {
                document.getElementById('pdfViewPane').classList.add('active');
            } else if (targetId === 'pngView') {
                document.getElementById('pngViewPane').classList.add('active');
            }
        });
    });

    // ==========================================================================
    // High-Resolution Image Zoom Controls
    // ==========================================================================

    zoomInBtn.addEventListener('click', () => {
        currentZoom = Math.min(currentZoom + 0.25, 4.0);
        applyZoom();
    });

    zoomOutBtn.addEventListener('click', () => {
        currentZoom = Math.max(currentZoom - 0.25, 0.5);
        applyZoom();
    });

    zoomResetBtn.addEventListener('click', () => {
        resetZoom();
    });

    previewImage.addEventListener('dblclick', () => {
        if (currentZoom !== 1.0) {
            resetZoom();
        } else {
            currentZoom = 2.0;
            applyZoom();
        }
    });

    function resetZoom() {
        currentZoom = 1.0;
        applyZoom();
    }

    function applyZoom() {
        previewImage.style.transform = `scale(${currentZoom})`;
        zoomLevelText.textContent = `${Math.round(currentZoom * 100)}%`;
    }

    // ==========================================================================
    // Modal Controller
    // ==========================================================================

    btnInfoModal.addEventListener('click', () => infoModal.classList.remove('hidden'));
    btnCloseModal.addEventListener('click', () => infoModal.classList.add('hidden'));
    btnModalOk.addEventListener('click', () => infoModal.classList.add('hidden'));

    infoModal.addEventListener('click', (e) => {
        if (e.target === infoModal) {
            infoModal.classList.add('hidden');
        }
    });

    // ==========================================================================
    // Toast Notification Utility
    // ==========================================================================

    function showToast(message, type = 'success') {
        const toastContainer = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const iconClass = type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation';
        toast.innerHTML = `<i class="fa-solid ${iconClass}"></i> <span>${escapeHtml(message)}</span>`;

        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.25s ease';
            setTimeout(() => toast.remove(), 250);
        }, 5000);
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
