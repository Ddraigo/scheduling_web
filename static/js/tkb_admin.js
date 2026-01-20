/**
 * TKB Admin - UI Module
 * Quản lý modal layering, button states, form validation
 */

const TKB = (() => {
    /**
     * FIX MODAL LAYERING (Task A)
     * Di chuyển modals ra khỏi stacking context của admin content
     * bằng cách append chúng vào body
     */
    function moveModalsToBody() {
        const modalIds = ['addScheduleModal', 'editScheduleModal', 'deleteConfirmModal', 'swapScheduleModal', 'restoreScheduleModal'];
        modalIds.forEach(id => {
            const modal = document.getElementById(id);
            if (modal && modal.parentElement) {
                // Remove từ current parent, append vào body
                modal.parentElement.removeChild(modal);
                document.body.appendChild(modal);
                
                // Ensure modal z-index trên backdrop
                modal.style.zIndex = '1050';
            }
        });
    }

    /**
     * Ensure loading overlay luôn dưới modals
     */
    function ensureLoadingOverlay() {
        const loading = document.getElementById('globalLoading');
        if (loading) {
            loading.style.zIndex = '1040';
        }
    }

    /**
     * Disable/enable button với helper text
     */
    function updateButtonState(btn, enabled, helperText = '') {
        if (!btn) return;
        btn.disabled = !enabled;
        btn.title = helperText;
        if (helperText) {
            btn.setAttribute('data-bs-toggle', 'tooltip');
            btn.setAttribute('data-bs-placement', 'bottom');
        }
    }

    /**
     * Highlight class chip khi selected
     */
    function highlightClassChip(chip, isSelected) {
        if (!chip) return;
        if (isSelected) {
            chip.classList.add('selected');
        } else {
            chip.classList.remove('selected');
        }
    }

    /**
     * Set button loading state (spinner + disabled)
     */
    function setButtonLoading(btn, loading, text = '') {
        if (!btn) return;
        btn.disabled = loading;
        if (loading) {
            btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>${text || 'Loading...'}`;
        } else {
            btn.innerHTML = text || btn.textContent;
        }
    }

    /**
     * Reset form sau khi submit thành công
     */
    function resetForm(form) {
        if (!form) return;
        form.reset();
        // Clear validation states
        form.querySelectorAll('.is-invalid').forEach(el => {
            el.classList.remove('is-invalid');
        });
        form.querySelectorAll('.invalid-feedback').forEach(el => {
            el.remove();
        });
    }

    /**
     * Validate form (check required fields)
     */
    function validateForm(form) {
        if (!form) return false;
        const inputs = form.querySelectorAll('[required]');
        let valid = true;
        inputs.forEach(input => {
            if (!input.value || input.value.trim() === '') {
                input.classList.add('is-invalid');
                valid = false;
            } else {
                input.classList.remove('is-invalid');
            }
        });
        return valid;
    }

    /**
     * Show inline error message
     */
    function showFieldError(fieldId, message) {
        const field = document.getElementById(fieldId);
        if (!field) return;
        field.classList.add('is-invalid');
        
        // Remove existing feedback
        const existing = field.parentElement.querySelector('.invalid-feedback');
        if (existing) existing.remove();
        
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback d-block';
        feedback.textContent = message;
        field.parentElement.appendChild(feedback);
    }

    /**
     * Clear field error
     */
    function clearFieldError(fieldId) {
        const field = document.getElementById(fieldId);
        if (!field) return;
        field.classList.remove('is-invalid');
        const feedback = field.parentElement.querySelector('.invalid-feedback');
        if (feedback) feedback.remove();
    }

    return {
        moveModalsToBody,
        ensureLoadingOverlay,
        updateButtonState,
        highlightClassChip,
        setButtonLoading,
        resetForm,
        validateForm,
        showFieldError,
        clearFieldError,
    };
})();

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    TKB.moveModalsToBody();
    TKB.ensureLoadingOverlay();
});
