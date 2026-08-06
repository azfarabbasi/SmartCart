/**
 * SmartCart - JavaScript Functions
 * Amazon-style E-commerce Frontend
 */

// ═══════════════════════════════════════════════════════════
// DOM Ready
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', function() {
    initializeSidebar();
    initializeAlerts();
    initializeDropdowns();
    initializeQuantitySelectors();
    initializeImageZoom();
    initializeFormValidation();
    initializeSearchEnhancements();
    initializeTooltips();
});

// ═══════════════════════════════════════════════════════════
// Password Toggle
// ═══════════════════════════════════════════════════════════
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const button = input.parentElement.querySelector('.password-toggle');
    const icon = button.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('bi-eye');
        icon.classList.add('bi-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('bi-eye-slash');
        icon.classList.add('bi-eye');
    }
}

// ═══════════════════════════════════════════════════════════
// Admin Sidebar Toggle
// ═══════════════════════════════════════════════════════════
function initializeSidebar() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.admin-sidebar');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });
        
        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(event) {
            if (window.innerWidth <= 992) {
                if (!sidebar.contains(event.target) && !sidebarToggle.contains(event.target)) {
                    sidebar.classList.remove('show');
                }
            }
        });
    }
}

// ═══════════════════════════════════════════════════════════
// Auto-dismiss Alerts
// ═══════════════════════════════════════════════════════════
function initializeAlerts() {
    const alerts = document.querySelectorAll('.alert-dismissible');
    
    alerts.forEach(function(alert) {
        // Auto dismiss after 5 seconds
        setTimeout(function() {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });
}

// ═══════════════════════════════════════════════════════════
// Dropdown Enhancements
// ═══════════════════════════════════════════════════════════
function initializeDropdowns() {
    // Keep dropdown open when clicking inside
    const dropdownMenus = document.querySelectorAll('.dropdown-menu');
    
    dropdownMenus.forEach(function(menu) {
        menu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    });
}

// ═══════════════════════════════════════════════════════════
// Quantity Selector Enhancements
// ═══════════════════════════════════════════════════════════
function initializeQuantitySelectors() {
    const quantitySelects = document.querySelectorAll('.quantity-form select');
    
    quantitySelects.forEach(function(select) {
        // Add visual feedback when changing quantity
        select.addEventListener('change', function() {
            const form = this.closest('form');
            const submitBtn = form.querySelector('button[type="submit"]');
            
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            }
        });
    });
}

// ═══════════════════════════════════════════════════════════
// Image Zoom on Hover (Product Detail)
// ═══════════════════════════════════════════════════════════
function initializeImageZoom() {
    const mainImage = document.getElementById('mainImage');
    
    if (mainImage) {
        const container = mainImage.closest('.product-detail-image');
        
        container.addEventListener('mousemove', function(e) {
            const rect = container.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width * 100;
            const y = (e.clientY - rect.top) / rect.height * 100;
            
            mainImage.style.transformOrigin = `${x}% ${y}%`;
            mainImage.style.transform = 'scale(1.5)';
        });
        
        container.addEventListener('mouseleave', function() {
            mainImage.style.transform = 'scale(1)';
        });
    }
}

// ═══════════════════════════════════════════════════════════
// Form Validation Enhancements
// ═══════════════════════════════════════════════════════════
function initializeFormValidation() {
    // Add validation to forms
    const forms = document.querySelectorAll('form');
    
    forms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            
            form.classList.add('was-validated');
        });
    });
    
    // Real-time validation for required fields
    const requiredInputs = document.querySelectorAll('input[required], select[required], textarea[required]');
    
    requiredInputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            if (this.value.trim() === '') {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            }
        });
        
        input.addEventListener('input', function() {
            if (this.value.trim() !== '') {
                this.classList.remove('is-invalid');
            }
        });
    });
}

// ═══════════════════════════════════════════════════════════
// Search Enhancements
// ═══════════════════════════════════════════════════════════
function initializeSearchEnhancements() {
    const searchInput = document.querySelector('.search-input');
    
    if (searchInput) {
        // Clear search on escape
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                this.value = '';
                this.blur();
            }
        });
        
        // Focus search on '/' key
        document.addEventListener('keydown', function(e) {
            if (e.key === '/' && document.activeElement !== searchInput) {
                e.preventDefault();
                searchInput.focus();
            }
        });
    }
}

// ═══════════════════════════════════════════════════════════
// Bootstrap Tooltips
// ═══════════════════════════════════════════════════════════
function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// ═══════════════════════════════════════════════════════════
// Add to Cart Animation
// ═══════════════════════════════════════════════════════════
function addToCartAnimation(button) {
    const originalContent = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding...';
    
    setTimeout(function() {
        button.innerHTML = '<i class="bi bi-check-lg me-2"></i>Added!';
        button.classList.remove('btn-warning');
        button.classList.add('btn-success');
        
        setTimeout(function() {
            button.innerHTML = originalContent;
            button.classList.remove('btn-success');
            button.classList.add('btn-warning');
            button.disabled = false;
        }, 1500);
    }, 500);
}

// ═══════════════════════════════════════════════════════════
// Confirm Delete
// ═══════════════════════════════════════════════════════════
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this item?');
}

// ═══════════════════════════════════════════════════════════
// Format Currency
// ═══════════════════════════════════════════════════════════
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2
    }).format(amount);
}

// ═══════════════════════════════════════════════════════════
// Format Date
// ═══════════════════════════════════════════════════════════
function formatDate(dateString) {
    const options = { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    };
    return new Date(dateString).toLocaleDateString('en-IN', options);
}

// ═══════════════════════════════════════════════════════════
// Debounce Function
// ═══════════════════════════════════════════════════════════
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

// ═══════════════════════════════════════════════════════════
// Print Invoice
// ═══════════════════════════════════════════════════════════
function printInvoice() {
    const customerInfo = document.getElementById('invoiceCustomerInfo');
    const orderItems = document.getElementById('invoiceOrderItems');
    const paymentInfo = document.getElementById('invoicePaymentInfo');

    if (!customerInfo || !orderItems) {
        window.print();
        return;
    }

    const orderTitleEl = document.querySelector('.order-info-header h2');
    const orderDateEl = document.querySelector('.order-info-header .order-date');
    const orderTitle = orderTitleEl ? orderTitleEl.textContent.trim() : 'Invoice';
    const orderDate = orderDateEl ? orderDateEl.textContent.trim() : '';

    const printWindow = window.open('', '_blank', 'noopener,noreferrer,width=900,height=650');
    if (!printWindow) {
        window.print();
        return;
    }

    const cssHref =
        (document.querySelector('link[href*="css/style.css"]') || {}).href || '';

    const bootstrapHref =
        (document.querySelector('link[href*="bootstrap"]') || {}).href ||
        'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css';

    printWindow.document.open();
    printWindow.document.write(`
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(orderTitle)}</title>
    <link rel="stylesheet" href="${bootstrapHref}">
    ${cssHref ? `<link rel="stylesheet" href="${cssHref}">` : ''}
    <style>
      body { background: #fff !important; }
      .print-wrap { padding: 24px; }
      .print-header { display:flex; align-items:flex-start; justify-content:space-between; gap: 16px; margin-bottom: 16px; }
      .print-header h2 { margin: 0; font-size: 20px; }
      .print-date { color: #6c757d; font-size: 14px; margin-top: 4px; }
      /* Hide anything interactive if present */
      button, a[href] { display: none !important; }
      @media print {
        .print-wrap { padding: 0; }
      }
    </style>
  </head>
  <body>
    <div class="print-wrap">
      <div class="print-header">
        <div>
          <h2>${escapeHtml(orderTitle)}</h2>
          ${orderDate ? `<div class="print-date">${escapeHtml(orderDate)}</div>` : ''}
        </div>
        <div><strong>SmartCart</strong></div>
      </div>

      ${customerInfo.outerHTML}
      ${orderItems.outerHTML}
      ${paymentInfo ? paymentInfo.outerHTML : ''}
    </div>
  </body>
</html>
    `);
    printWindow.document.close();

    // Ensure styles have a moment to load, then print.
    printWindow.focus();
    setTimeout(() => {
        printWindow.print();
        // Close after printing (or after the dialog is dismissed)
        setTimeout(() => printWindow.close(), 250);
    }, 350);
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ═══════════════════════════════════════════════════════════
// Copy to Clipboard
// ═══════════════════════════════════════════════════════════
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('Copied to clipboard!', 'success');
    }).catch(function(err) {
        console.error('Failed to copy: ', err);
    });
}

// ═══════════════════════════════════════════════════════════
// Show Toast Notification
// ═══════════════════════════════════════════════════════════
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'primary'}`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toast, { autohide: true, delay: 3000 });
    bsToast.show();
    
    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

// ═══════════════════════════════════════════════════════════
// Lazy Load Images
// ═══════════════════════════════════════════════════════════
function lazyLoadImages() {
    const images = document.querySelectorAll('img[data-src]');
    
    const imageObserver = new IntersectionObserver(function(entries, observer) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
                observer.unobserve(img);
            }
        });
    });
    
    images.forEach(function(img) {
        imageObserver.observe(img);
    });
}

// ═══════════════════════════════════════════════════════════
// Smooth Scroll to Top
// ═══════════════════════════════════════════════════════════
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// ═══════════════════════════════════════════════════════════
// Handle Image Upload Preview
// ═══════════════════════════════════════════════════════════
function previewImage(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('imagePreview');
            const placeholder = document.getElementById('uploadPlaceholder');
            
            if (preview) {
                preview.src = e.target.result;
                preview.classList.remove('d-none');
            }
            if (placeholder) {
                placeholder.classList.add('d-none');
            }
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// ═══════════════════════════════════════════════════════════
// Stock Warning
// ═══════════════════════════════════════════════════════════
function checkLowStock() {
    const stockElements = document.querySelectorAll('.stock-number');
    
    stockElements.forEach(function(el) {
        const stock = parseInt(el.textContent);
        if (stock === 0) {
            el.closest('tr').classList.add('table-danger');
        } else if (stock <= 10) {
            el.closest('tr').classList.add('table-warning');
        }
    });
}

// ═══════════════════════════════════════════════════════════
// Initialize Additional Features
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', function() {
    lazyLoadImages();
    checkLowStock();
    
    // Add loading state to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                const originalText = submitBtn.innerHTML;
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                
                // Re-enable after 10 seconds as fallback
                setTimeout(function() {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }, 10000);
            }
        });
    });
});

// ═══════════════════════════════════════════════════════════
// Export Functions (if using modules)
// ═══════════════════════════════════════════════════════════
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        togglePassword,
        addToCartAnimation,
        confirmDelete,
        formatCurrency,
        formatDate,
        showToast,
        scrollToTop,
        previewImage
    };
}
