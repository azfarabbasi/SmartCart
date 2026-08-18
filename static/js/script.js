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
    initializeProductGallerySlider();
    initializeFormValidation();
    initializeSearchEnhancements();
    initializeTooltips();
    lazyLoadImages();
    checkLowStock();
    initializeFormLoadingState();
    initializeUnobtrusiveHandlers();
});

// ═══════════════════════════════════════════════════════════
// Unobtrusive event bindings
// (Our CSP has no 'unsafe-inline' in script-src, so inline
// onclick/onchange/onsubmit attributes are silently ignored by
// the browser -- every interactive behavior gets bound here instead.)
// ═══════════════════════════════════════════════════════════
function initializeUnobtrusiveHandlers() {
    // Password show/hide toggle buttons
    document.querySelectorAll('.password-toggle').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const wrapper = btn.closest('.password-input-wrapper');
            const input = wrapper ? wrapper.querySelector('input') : null;
            if (input) togglePassword(input.id);
        });
    });

    // Product image file-input preview (add/edit product forms)
    const imageInput = document.getElementById('image');
    if (imageInput) {
        imageInput.addEventListener('change', function() {
            previewImage(this);
        });
    }

    // "Back to top" footer link
    document.querySelectorAll('.js-back-to-top').forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });

    // Auto-submit selects/checkboxes (quantity dropdowns, filter dropdowns, etc.)
    document.querySelectorAll('.js-auto-submit').forEach(function(el) {
        el.addEventListener('change', function() {
            el.form.submit();
        });
    });

    // Confirm-before-submit forms (delete buttons, destructive actions)
    document.querySelectorAll('form[data-confirm]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            if (!window.confirm(form.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    // Admin product form: clicking the drop-zone opens the file picker and previews image
    const uploadArea = document.getElementById('imageUploadArea');
    const imageField = document.getElementById('image');
    const imagePreview = document.getElementById('imagePreview');
    const uploadPlaceholder = document.getElementById('uploadPlaceholder');
    if (uploadArea && imageField) {
        uploadArea.addEventListener('click', function (e) {
            if (e.target !== imageField) {
                imageField.click();
            }
        });
        imageField.addEventListener('change', function () {
            if (this.files && this.files[0]) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    if (imagePreview) {
                        imagePreview.src = e.target.result;
                        imagePreview.classList.remove('d-none');
                    }
                    if (uploadPlaceholder) {
                        uploadPlaceholder.classList.add('d-none');
                    }
                };
                reader.readAsDataURL(this.files[0]);
            }
        });
    }

    // Checkout payment method selector toggle
    const paymentRadios = document.querySelectorAll('.payment-method-radio');
    const bankDetailsBox = document.getElementById('bankTransferDetails');
    const paymentProofInput = document.getElementById('payment_proof');

    function updatePaymentMethodView() {
        const selected = document.querySelector('.payment-method-radio:checked');
        if (!selected || !bankDetailsBox) return;

        if (selected.value === 'bank_transfer') {
            bankDetailsBox.style.display = 'block';
            if (paymentProofInput) paymentProofInput.required = true;
        } else {
            bankDetailsBox.style.display = 'none';
            if (paymentProofInput) {
                paymentProofInput.required = false;
                paymentProofInput.value = '';
            }
        }
    }

    if (paymentRadios.length > 0) {
        paymentRadios.forEach(function(radio) {
            radio.addEventListener('change', updatePaymentMethodView);
        });
        updatePaymentMethodView();
    }

    // Admin product form: cap how many gallery files can be attached at once
    const mediaField = document.getElementById('media');
    if (mediaField && mediaField.dataset.maxMedia) {
        const maxMedia = parseInt(mediaField.dataset.maxMedia, 10);
        mediaField.addEventListener('change', function () {
            if (this.files.length > maxMedia) {
                showToast('You can upload at most ' + maxMedia + ' media items per product.', 'error');
                this.value = '';
            }
        });
    }

    // Admin Coupons: Discount Type Switcher (Percentage vs Fixed Cost)
    const typePercentage = document.getElementById('typePercentage');
    const typeFixed = document.getElementById('typeFixed');
    const sectionPercent = document.getElementById('sectionPercentage');
    const sectionFixed = document.getElementById('sectionFixed');
    const inputPercent = document.getElementById('inputPercent');
    const inputFixed = document.getElementById('inputFixed');

    if (typePercentage && typeFixed && sectionPercent && sectionFixed) {
        function syncCouponDiscountType() {
            if (typeFixed.checked) {
                sectionFixed.classList.remove('d-none');
                sectionPercent.classList.add('d-none');
                if (inputFixed) {
                    inputFixed.required = true;
                    inputFixed.disabled = false;
                }
                if (inputPercent) {
                    inputPercent.required = false;
                    inputPercent.disabled = true;
                }
            } else {
                sectionPercent.classList.remove('d-none');
                sectionFixed.classList.add('d-none');
                if (inputPercent) {
                    inputPercent.required = true;
                    inputPercent.disabled = false;
                }
                if (inputFixed) {
                    inputFixed.required = false;
                    inputFixed.disabled = true;
                }
            }
        }

        typePercentage.addEventListener('change', syncCouponDiscountType);
        typeFixed.addEventListener('change', syncCouponDiscountType);
        document.querySelectorAll('label[for="typePercentage"], label[for="typeFixed"]').forEach(function(lbl) {
            lbl.addEventListener('click', function() {
                setTimeout(syncCouponDiscountType, 10);
            });
        });
        syncCouponDiscountType();
    }

    // Checkout: live "this is what your points are worth" hint
    const pointsInput = document.getElementById('pointsToRedeem');
    const pointsPreview = document.getElementById('pointsDiscountPreview');
    if (pointsInput && pointsPreview) {
        pointsInput.addEventListener('input', function () {
            const pts = parseInt(this.value, 10) || 0;
            pointsPreview.textContent =
                'Discount: Rs. ' + (pts / 10).toFixed(2) + ' (confirmed at checkout)';
        });
    }

    // Registration: live password-match indicator + hard submit block on mismatch
    const registerForm = document.getElementById('registerForm');
    const pw = document.getElementById('password');
    const confirmPw = document.getElementById('confirm_password');
    const matchMsg = document.getElementById('passwordMatchMsg');
    if (registerForm && pw && confirmPw && matchMsg) {
        const checkMatch = function() {
            if (!confirmPw.value) {
                matchMsg.textContent = '';
                matchMsg.className = 'form-text';
                confirmPw.setCustomValidity('');
                return;
            }
            if (pw.value === confirmPw.value) {
                matchMsg.textContent = 'Passwords match.';
                matchMsg.className = 'form-text text-success';
                confirmPw.setCustomValidity('');
            } else {
                matchMsg.textContent = 'Passwords do not match.';
                matchMsg.className = 'form-text text-danger';
                confirmPw.setCustomValidity('Passwords do not match.');
            }
        };
        pw.addEventListener('input', checkMatch);
        confirmPw.addEventListener('input', checkMatch);
        registerForm.addEventListener('submit', function(e) {
            if (pw.value !== confirmPw.value) {
                e.preventDefault();
                checkMatch();
                confirmPw.reportValidity();
            }
        });
    }
}

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
    const backdrop = document.getElementById('sidebarBackdrop');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
            if (backdrop) backdrop.classList.toggle('show');
        });

        // The backdrop is a real element covering the rest of the page while
        // the sidebar is open, so a click on it is fully consumed here and
        // can never fall through to a link/button underneath.
        if (backdrop) {
            backdrop.addEventListener('click', function(event) {
                event.preventDefault();
                event.stopPropagation();
                sidebar.classList.remove('show');
                backdrop.classList.remove('show');
            });
        }
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
// Product Gallery Slider & Thumbnail Controller
// ═══════════════════════════════════════════════════════════
function initializeProductGallerySlider() {
    const carouselEl = document.getElementById('productGalleryCarousel');
    if (!carouselEl) return;

    const counterSpan = document.getElementById('galleryCurrentIndex');
    const thumbButtons = document.querySelectorAll('.gallery-thumb-btn');

    // Bootstrap Carousel instance
    const carousel = (typeof bootstrap !== 'undefined' && bootstrap.Carousel)
        ? bootstrap.Carousel.getOrCreateInstance(carouselEl, { interval: false, ride: false, wrap: true })
        : null;

    // Function to update active thumbnail and counter
    function updateActiveState(index) {
        if (counterSpan) {
            counterSpan.textContent = index + 1;
        }

        thumbButtons.forEach(function(btn, i) {
            if (i === index) {
                btn.classList.add('active');
                btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            } else {
                btn.classList.remove('active');
            }
        });
    }

    // Listen to Bootstrap carousel slide events
    carouselEl.addEventListener('slide.bs.carousel', function(e) {
        updateActiveState(e.to);
    });

    // Thumbnail click & hover interactions
    thumbButtons.forEach(function(btn, index) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            if (carousel) {
                carousel.to(index);
            }
            updateActiveState(index);
        });

        // Instant preview switch on mouse enter (Amazon / Daraz style)
        btn.addEventListener('mouseenter', function() {
            if (carousel) {
                carousel.to(index);
            }
            updateActiveState(index);
        });
    });

    // Touch Swipe Support for Mobile & Tablets
    let touchStartX = 0;
    let touchEndX = 0;

    carouselEl.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    carouselEl.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        const diffX = touchStartX - touchEndX;
        if (Math.abs(diffX) > 40) {
            if (diffX > 0 && carousel) {
                carousel.next();
            } else if (diffX < 0 && carousel) {
                carousel.prev();
            }
        }
    }, { passive: true });

    // Keyboard Arrow Keys (Left / Right) when focused
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft' && carousel && document.activeElement.tagName !== 'INPUT') {
            carousel.prev();
        } else if (e.key === 'ArrowRight' && carousel && document.activeElement.tagName !== 'INPUT') {
            carousel.next();
        }
    });
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
        const file = input.files[0];
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('imagePreview');
            const placeholder = document.getElementById('uploadPlaceholder');

            if (preview) {
                if (file.type.startsWith('video/')) {
                    preview.setAttribute('src', '');
                } else {
                    preview.src = e.target.result;
                }
                preview.classList.remove('d-none');
            }
            if (placeholder) {
                placeholder.classList.add('d-none');
            }
        };
        reader.readAsDataURL(file);
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
// Loading State for Form Submissions
// ═══════════════════════════════════════════════════════════
function initializeFormLoadingState() {
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
}

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
