document.addEventListener('DOMContentLoaded', () => {
  const codeBlocks = document.querySelectorAll('div.highlight');

  codeBlocks.forEach((block) => {
    if (block.querySelector('.polyfi-copy-button')) {
      return;
    }

    const codeElement = block.querySelector('pre');
    if (!codeElement) {
      return;
    }

    block.style.position = 'relative';

    const button = document.createElement('button');
    button.className = 'polyfi-copy-button';
    button.type = 'button';
    button.textContent = 'Copy';
    button.setAttribute('aria-label', 'Copy code block');
    button.style.position = 'absolute';
    button.style.top = '0.5rem';
    button.style.right = '0.5rem';
    button.style.padding = '0.25rem 0.5rem';
    button.style.cursor = 'pointer';
    button.style.fontSize = '0.75rem';
    button.style.borderRadius = '0.25rem';
    button.style.border = '1px solid #d1d5db';
    button.style.background = '#ffffff';

    button.addEventListener('click', async () => {
      const codeText = codeElement.innerText;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(codeText);
        } else {
          const textArea = document.createElement('textarea');
          textArea.value = codeText;
          textArea.style.position = 'fixed';
          textArea.style.opacity = '0';
          document.body.appendChild(textArea);
          textArea.focus();
          textArea.select();
          document.execCommand('copy');
          textArea.remove();
        }

        button.textContent = 'Copied!';
      } catch {
        button.textContent = 'Unable to copy';
      }
      setTimeout(() => {
        button.textContent = 'Copy';
      }, 1500);
    });

    block.appendChild(button);
  });
});
