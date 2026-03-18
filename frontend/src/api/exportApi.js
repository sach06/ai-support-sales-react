import api from './client';

export const exportDocx = async (profile, customerName) => {
    const response = await api.post('/export/docx',
        { profile, customer_name: customerName },
        { responseType: 'blob' }
    );

    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }));
    const link = document.createElement('a');
    link.href = url;

    // Attempt to extract filename from content-disposition header if available, otherwise fallback
    const contentDisposition = response.headers['content-disposition'];
    const timestamp = new Date().toISOString().replace(/T/, '_').replace(/:/g, '-').split('.')[0];
    const safeName = customerName.replace(/[^a-z0-9]/gi, '_').toLowerCase();

    let fileName = `${safeName}_${timestamp}.docx`;
    if (contentDisposition) {
        const fileNameMatch = contentDisposition.match(/filename\*?=['"]?(?:UTF-\d['"]*)?([^;\r\n"']*)['"]?;?/);
        if (fileNameMatch && fileNameMatch.length === 2) {
            fileName = decodeURIComponent(fileNameMatch[1]);
        }
    }

    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    link.remove();
};

export const exportPdf = async (profile, customerName) => {
    const response = await api.post('/export/pdf',
        { profile, customer_name: customerName },
        { responseType: 'blob' }
    );

    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = url;

    const contentDisposition = response.headers['content-disposition'];
    const timestamp = new Date().toISOString().replace(/T/, '_').replace(/:/g, '-').split('.')[0];
    const safeName = customerName.replace(/[^a-z0-9]/gi, '_').toLowerCase();

    let fileName = `${safeName}_${timestamp}.pdf`;
    if (contentDisposition) {
        const fileNameMatch = contentDisposition.match(/filename\*?=['"]?(?:UTF-\d['"]*)?([^;\r\n"']*)['"]?;?/);
        if (fileNameMatch && fileNameMatch.length === 2) {
            fileName = decodeURIComponent(fileNameMatch[1]);
        }
    }

    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    link.remove();
};

export const exportPptx = async (profile, customerName) => {
    const response = await api.post('/export/pptx',
        { profile, customer_name: customerName },
        { responseType: 'blob' }
    );

    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' }));
    const link = document.createElement('a');
    link.href = url;

    const contentDisposition = response.headers['content-disposition'];
    const timestamp = new Date().toISOString().replace(/T/, '_').replace(/:/g, '-').split('.')[0];
    const safeName = customerName.replace(/[^a-z0-9]/gi, '_').toLowerCase();

    let fileName = `${safeName}_${timestamp}.pptx`;
    if (contentDisposition) {
        const fileNameMatch = contentDisposition.match(/filename\*?=['"]?(?:UTF-\d['"]*)?([^;\r\n"']*)['"]?;?/);
        if (fileNameMatch && fileNameMatch.length === 2) {
            fileName = decodeURIComponent(fileNameMatch[1]);
        }
    }

    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    link.remove();
};
