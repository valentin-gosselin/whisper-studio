/**
 * Custom Select - Reusable component for styled select dropdowns
 * Usage: initCustomSelect(selectElement, options)
 */

function initCustomSelect(selectElement, options = {}) {
    const {
        onChange = null,
        placeholder = 'Select an option'
    } = options;

    // Get options from the native select
    const nativeOptions = Array.from(selectElement.options).map(opt => ({
        value: opt.value,
        text: opt.textContent,
        selected: opt.selected
    }));

    // Create custom select HTML
    const customSelectHTML = `
        <div class="custom-select" data-name="${selectElement.name}">
            <div class="select-trigger">
                <span class="select-label">${nativeOptions.find(o => o.selected)?.text || placeholder}</span>
                <svg class="select-arrow" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
            </div>
            <div class="select-options">
                ${nativeOptions.map(opt => `
                    <div class="select-option ${opt.selected ? 'active' : ''}"
                         data-value="${opt.value}">
                        ${opt.text}
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    // Replace native select with custom select
    const customSelectWrapper = document.createElement('div');
    customSelectWrapper.innerHTML = customSelectHTML;
    const customSelectEl = customSelectWrapper.firstElementChild;

    selectElement.style.display = 'none';
    selectElement.parentNode.insertBefore(customSelectEl, selectElement.nextSibling);

    // Get elements
    const trigger = customSelectEl.querySelector('.select-trigger');
    const label = customSelectEl.querySelector('.select-label');
    const optionsContainer = customSelectEl.querySelector('.select-options');
    const optionElements = customSelectEl.querySelectorAll('.select-option');

    // Toggle dropdown
    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        customSelectEl.classList.toggle('open');
    });

    // Option selection
    optionElements.forEach(optionEl => {
        optionEl.addEventListener('click', () => {
            const value = optionEl.dataset.value;
            const text = optionEl.textContent.trim();

            // Update UI
            label.textContent = text;
            optionElements.forEach(el => el.classList.remove('active'));
            optionEl.classList.add('active');

            // Update native select
            selectElement.value = value;

            // Trigger change event on native select
            const event = new Event('change', { bubbles: true });
            selectElement.dispatchEvent(event);

            // Call custom onChange if provided
            if (onChange) {
                onChange(value, text);
            }

            // Close dropdown
            customSelectEl.classList.remove('open');
        });
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
        if (!customSelectEl.contains(e.target)) {
            customSelectEl.classList.remove('open');
        }
    });

    return {
        element: customSelectEl,
        setValue: (value) => {
            const option = Array.from(optionElements).find(el => el.dataset.value === value);
            if (option) {
                option.click();
            }
        },
        getValue: () => selectElement.value,
        destroy: () => {
            customSelectEl.remove();
            selectElement.style.display = '';
        }
    };
}

/**
 * Initialize all custom selects on the page
 * Add data-custom-select attribute to any select you want to convert
 */
function initAllCustomSelects() {
    const selects = document.querySelectorAll('select[data-custom-select]');
    const instances = [];

    selects.forEach(select => {
        instances.push(initCustomSelect(select));
    });

    return instances;
}

// Auto-init on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAllCustomSelects);
} else {
    initAllCustomSelects();
}
