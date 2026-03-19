import api from './client';

const EXPORT_TIMEOUT_MS = 240000;

const extractFileNameFromHeaders = (headers, fallbackName) => {
    const contentDisposition = headers?.['content-disposition'];
    if (!contentDisposition) return fallbackName;

    const utf8Match = contentDisposition.match(/filename\*=utf-8''([^;\r\n]+)/i);
    if (utf8Match && utf8Match[1]) {
        return decodeURIComponent(utf8Match[1]);
    }

    const fileNameMatch = contentDisposition.match(/filename=['"]?([^;\r\n"']+)['"]?/i);
    if (fileNameMatch && fileNameMatch[1]) {
        return fileNameMatch[1];
    }

    return fallbackName;
};

const sanitizeFileStem = (customerName) => {
    return customerName.replace(/[^a-z0-9]/gi, '_').toLowerCase();
};

const timestampedFallbackName = (customerName, extension) => {
    const timestamp = new Date().toISOString().replace(/T/, '_').replace(/:/g, '-').split('.')[0];
    return `${sanitizeFileStem(customerName)}_${timestamp}.${extension}`;
};

const parseExportError = async (err) => {
    const status = err?.response?.status;
    const data = err?.response?.data;

    // Axios returns a Blob when responseType is blob even for error responses.
    if (data instanceof Blob) {
        try {
            const text = await data.text();
            const parsed = JSON.parse(text);
            const detail = parsed?.detail || parsed?.message || text;
            return `Export failed (${status || 'error'}): ${String(detail).slice(0, 320)}`;
        } catch (_) {
            return `Export failed (${status || 'error'}).`;
        }
    }

    const detail = err?.response?.data?.detail || err?.message || 'Unknown export error.';
    return `Export failed (${status || 'error'}): ${String(detail).slice(0, 320)}`;
};

const downloadBlob = (blob, fileName) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
};

export const exportDocx = async (profile, customerName) => {
    try {
        const response = await api.post('/export/docx',
            { profile, customer_name: customerName },
            { responseType: 'blob', timeout: EXPORT_TIMEOUT_MS }
        );

        const fallback = timestampedFallbackName(customerName, 'docx');
        const fileName = extractFileNameFromHeaders(response.headers, fallback);
        downloadBlob(
            new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }),
            fileName
        );
    } catch (err) {
        throw new Error(await parseExportError(err));
    }
};

export const exportPdf = async (profile, customerName) => {
    try {
        const response = await api.post('/export/pdf',
            { profile, customer_name: customerName },
            { responseType: 'blob', timeout: EXPORT_TIMEOUT_MS }
        );

        const fallback = timestampedFallbackName(customerName, 'pdf');
        const fileName = extractFileNameFromHeaders(response.headers, fallback);
        downloadBlob(new Blob([response.data], { type: 'application/pdf' }), fileName);
    } catch (err) {
        throw new Error(await parseExportError(err));
    }
};

export const exportPptx = async (profile, customerName) => {
    try {
        const response = await api.post('/export/pptx',
            { profile, customer_name: customerName },
            { responseType: 'blob', timeout: EXPORT_TIMEOUT_MS }
        );

        const fallback = timestampedFallbackName(customerName, 'pptx');
        const fileName = extractFileNameFromHeaders(response.headers, fallback);
        downloadBlob(
            new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' }),
            fileName
        );
    } catch (err) {
        throw new Error(await parseExportError(err));
    }
};
