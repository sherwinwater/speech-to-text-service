const MODEL_STATE = {
    upload: 'tiny',
    record: 'tiny',
    live: 'tiny',
};

const LABELS = {
    tiny: 'Fast',
    base: 'Balanced',
    small: 'Accurate',
};

function updateButtons(group, activeButton, buttons) {
    buttons.forEach(btn => {
        const isActive = btn === activeButton;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-pressed', String(isActive));
    });
}

export function initModelSelectors() {
    document.querySelectorAll('.model-select').forEach(container => {
        const group = container.dataset.group;
        if (!group) {
            return;
        }
        const buttons = Array.from(container.querySelectorAll('button[data-size]'));
        buttons.forEach(btn => {
            const size = btn.dataset.size;
            if (!size) {
                return;
            }

            if (btn.classList.contains('active')) {
                MODEL_STATE[group] = size;
            }

            btn.addEventListener('click', () => {
                MODEL_STATE[group] = size;
                updateButtons(group, btn, buttons);
            });

            btn.setAttribute(
                'title',
                LABELS[size] ? `${LABELS[size]} (${size})` : size
            );
        });
    });
}

export function getModelSize(group) {
    return MODEL_STATE[group] || 'tiny';
}
