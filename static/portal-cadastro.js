document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('cadastro-form');
    const password = document.getElementById('senha');
    const confirmation = document.getElementById('confirmar_senha');
    if (!form || !password || !confirmation) return;

    const rules = {
        length: document.getElementById('rule-length'),
        lower: document.getElementById('rule-lower'),
        upper: document.getElementById('rule-upper'),
        digit: document.getElementById('rule-digit'),
        match: document.getElementById('rule-match'),
    };

    const refreshRules = () => {
        const value = password.value;
        const started = value.length > 0 || confirmation.value.length > 0;
        const checks = {
            length: value.length >= 8 && value.length <= 128 && value.trim() === value,
            lower: /\p{Ll}/u.test(value),
            upper: /\p{Lu}/u.test(value),
            digit: /\p{Nd}/u.test(value),
            match: confirmation.value.length > 0 && value === confirmation.value,
        };
        Object.entries(checks).forEach(([key, valid]) => {
            rules[key].classList.toggle('met', valid);
            rules[key].classList.toggle('unmet', started && !valid);
        });
        confirmation.setCustomValidity(confirmation.value && !checks.match ? 'As senhas não são iguais.' : '');
        return Object.values(checks).every(Boolean);
    };

    password.addEventListener('input', refreshRules);
    confirmation.addEventListener('input', refreshRules);
    document.querySelectorAll('[data-toggle-password]').forEach((button) => {
        button.addEventListener('click', () => {
            const input = document.getElementById(button.dataset.togglePassword);
            const visible = input.type === 'password';
            input.type = visible ? 'text' : 'password';
            button.textContent = visible ? 'Ocultar' : 'Mostrar';
            button.setAttribute('aria-label', `${visible ? 'Ocultar' : 'Mostrar'} ${input === password ? 'senha' : 'confirmação da senha'}`);
        });
    });
    form.addEventListener('submit', (event) => {
        const validPassword = refreshRules();
        if (!form.checkValidity() || !validPassword) {
            event.preventDefault();
            if (!validPassword) (password.value !== confirmation.value && confirmation.value ? confirmation : password).focus();
            form.reportValidity();
        }
    });
});

