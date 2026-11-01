(() => {
  const DEFAULT_AUTO_DISMISS_MS = 3000;

  function closeAlert(alertEl) {
    if (window.bootstrap?.Alert) {
      window.bootstrap.Alert.getOrCreateInstance(alertEl).close();
      window.setTimeout(() => alertEl.remove(), 600);
      return;
    }

    alertEl.classList.remove('show');
    window.setTimeout(() => alertEl.remove(), 200);
  }

  function initAutoDismissAlerts() {
    document.querySelectorAll('.app-alert').forEach((alertEl) => {
      if (alertEl.dataset.autodismissInitialized === '1') return;
      alertEl.dataset.autodismissInitialized = '1';

      const configured = Number.parseInt(alertEl.dataset.autodismissMs, 10);
      const timeoutMs = Number.isFinite(configured) ? configured : DEFAULT_AUTO_DISMISS_MS;
      if (timeoutMs < 0) return;

      window.setTimeout(() => {
        if (!document.body.contains(alertEl)) return;
        closeAlert(alertEl);
      }, timeoutMs);
    });
  }

  function initPasswordToggles() {
    document.querySelectorAll('[data-password-toggle]').forEach((button) => {
      if (button.dataset.passwordToggleInitialized === '1') return;
      button.dataset.passwordToggleInitialized = '1';

      const targetSelector = button.getAttribute('data-target');
      const input = targetSelector ? document.querySelector(targetSelector) : null;
      if (!input) return;

      const updateIcon = () => {
        const isText = input.type === 'text';
        button.setAttribute('aria-pressed', isText ? 'true' : 'false');
        button.dataset.state = isText ? 'visible' : 'hidden';
      };

      button.addEventListener('click', () => {
        input.type = input.type === 'password' ? 'text' : 'password';
        updateIcon();
        input.focus();
      });

      updateIcon();
    });
  }

  function initOtpBoxes() {
    document.querySelectorAll('[data-otp-boxes]').forEach((container) => {
      if (container.dataset.otpInitialized === '1') return;
      container.dataset.otpInitialized = '1';

      const targetSelector = container.getAttribute('data-target');
      const hiddenInput = targetSelector ? document.querySelector(targetSelector) : null;
      if (!hiddenInput) return;

      const inputs = Array.from(container.querySelectorAll('input.otp-box'));
      if (!inputs.length) return;

      const setHidden = () => {
        hiddenInput.value = inputs.map((i) => i.value).join('').replace(/\D/g, '').slice(0, inputs.length);
      };

      const focusIndex = (idx) => {
        const el = inputs[idx];
        if (!el) return;
        el.focus();
        el.select();
      };

      inputs.forEach((input, idx) => {
        input.addEventListener('input', () => {
          input.value = (input.value || '').replace(/\D/g, '').slice(0, 1);
          setHidden();
          if (input.value && idx < inputs.length - 1) {
            focusIndex(idx + 1);
          }
        });

        input.addEventListener('keydown', (event) => {
          if (event.key === 'Backspace' && !input.value && idx > 0) {
            event.preventDefault();
            inputs[idx - 1].value = '';
            setHidden();
            focusIndex(idx - 1);
          }
          if (event.key === 'ArrowLeft' && idx > 0) {
            event.preventDefault();
            focusIndex(idx - 1);
          }
          if (event.key === 'ArrowRight' && idx < inputs.length - 1) {
            event.preventDefault();
            focusIndex(idx + 1);
          }
        });

        input.addEventListener('paste', (event) => {
          const text = (event.clipboardData?.getData('text') || '').replace(/\D/g, '');
          if (!text) return;
          event.preventDefault();
          const chars = text.slice(0, inputs.length - idx).split('');
          chars.forEach((ch, offset) => {
            const target = inputs[idx + offset];
            if (target) target.value = ch;
          });
          setHidden();
          const next = Math.min(idx + chars.length, inputs.length - 1);
          focusIndex(next);
        });
      });

      setHidden();
    });
  }

  initAutoDismissAlerts();
  initPasswordToggles();
  initOtpBoxes();
  document.addEventListener('DOMContentLoaded', initAutoDismissAlerts);
  document.addEventListener('DOMContentLoaded', initPasswordToggles);
  document.addEventListener('DOMContentLoaded', initOtpBoxes);
})();
