// Función para inicializar los tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Manejar el botón de copiar al portapapeles
    document.querySelectorAll('.copy-btn').forEach(button => {
        button.addEventListener('click', function() {
            const url = this.getAttribute('data-url');
            navigator.clipboard.writeText(url).then(() => {
                // Cambiar el icono temporalmente para indicar éxito
                const icon = this.querySelector('i');
                const originalClass = icon.className;
                icon.className = 'bi bi-check';
                
                // Restaurar el icono después de 2 segundos
                setTimeout(() => {
                    icon.className = originalClass;
                }, 2000);
            });
        });
    });
    
    // Manejar el formulario de búsqueda en la barra de navegación
    const searchForm = document.querySelector('form.d-flex');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const searchInput = this.querySelector('input[name="search"]');
            if (searchInput && searchInput.value.trim()) {
                window.location.href = `/?search=${encodeURIComponent(searchInput.value.trim())}`;
            }
        });
    }
    
    // Cargar dinámicamente el contenido de los tags
    loadTagHierarchy();
});

// Función para cargar la jerarquía de tags
function loadTagHierarchy() {
    const tagTree = document.getElementById('tagTree');
    if (!tagTree) return;
    
    fetch('/api/tag_hierarchy')
        .then(response => response.json())
        .then(tags => {
            tagTree.innerHTML = buildTagTree(tags);
            
            // Agregar manejadores de eventos a los enlaces de tags
            document.querySelectorAll('.tag-link').forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    const tagName = this.getAttribute('data-tag');
                    window.location.href = `/?tag=${encodeURIComponent(tagName)}`;
                });
            });
        })
        .catch(error => {
            console.error('Error al cargar la jerarquía de tags:', error);
            tagTree.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    Error al cargar los tags. Por favor, inténtalo de nuevo más tarde.
                </div>
            `;
        });
}

// Función para construir el árbol de tags
function buildTagTree(tags, level = 0) {
    if (!tags || tags.length === 0) return '';
    
    let html = '<ul class="list-unstyled">';
    
    tags.forEach(tag => {
        const isActive = window.location.search.includes(`tag=${encodeURIComponent(tag.name)}`);
        const paddingLeft = 15 + (tag.level * 15);
        const hasChildren = tag.children && tag.children.length > 0;
        
        html += `
            <li class="mb-1" style="padding-left: ${paddingLeft}px">
                <div class="d-flex align-items-center">
                    ${hasChildren ? `
                        <button class="btn btn-sm btn-link p-0 me-1 toggle-children" 
                                style="width: 20px; text-align: left;"
                                data-bs-toggle="collapse" 
                                data-bs-target="#tag-${tag.id}">
                            <i class="bi bi-caret-right-fill"></i>
                        </button>
                    ` : '<span style="width: 20px; display: inline-block;"></span>'}
                    
                    <a href="#" class="tag-link text-decoration-none ${isActive ? 'active' : ''}" 
                       data-tag="${tag.name}">
                        <i class="bi ${hasChildren ? 'bi-folder' : 'bi-tag'}"></i> 
                        ${tag.name}
                    </a>
                </div>
                
                ${hasChildren ? `
                    <div class="collapse ${level < 1 ? 'show' : ''}" id="tag-${tag.id}">
                        ${buildTagTree(tag.children, level + 1)}
                    </div>
                ` : ''}
            </li>
        `;
    });
    
    html += '</ul>';
    return html;
}

// Manejar el clic en los botones de alternar hijos
document.addEventListener('click', function(e) {
    if (e.target.closest('.toggle-children')) {
        const button = e.target.closest('.toggle-children');
        const icon = button.querySelector('i');
        
        // Alternar entre los iconos de flecha
        if (icon.classList.contains('bi-caret-right-fill')) {
            icon.classList.remove('bi-caret-right-fill');
            icon.classList.add('bi-caret-down-fill');
        } else {
            icon.classList.remove('bi-caret-down-fill');
            icon.classList.add('bi-caret-right-fill');
        }
    }
});

// Función para formatear fechas
function formatDate(dateString) {
    if (!dateString) return '';
    
    const options = { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    
    return new Date(dateString).toLocaleDateString('es-ES', options);
}

// Función para mostrar notificaciones toast
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;
    
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.style.marginBottom = '0.5rem';
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                    data-bs-dismiss="toast" aria-label="Cerrar"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 3000
    });
    
    bsToast.show();
    
    // Eliminar el toast del DOM después de que se oculte
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

// Manejar el envío de formularios con AJAX
document.addEventListener('submit', function(e) {
    const form = e.target;
    
    // Solo manejar formularios con data-ajax="true"
    if (form.getAttribute('data-ajax') !== 'true') return;
    
    e.preventDefault();
    
    const formData = new FormData(form);
    const submitButton = form.querySelector('[type="submit"]');
    const originalButtonText = submitButton ? submitButton.innerHTML : '';
    
    // Mostrar indicador de carga
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            Procesando...
        `;
    }
    
    fetch(form.action, {
        method: form.method,
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.redirect) {
            window.location.href = data.redirect;
        } else if (data.message) {
            showToast(data.message, data.status || 'success');
            
            // Recargar la página si es necesario
            if (data.reload) {
                setTimeout(() => window.location.reload(), 1500);
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Ocurrió un error al procesar la solicitud', 'danger');
    })
    .finally(() => {
        // Restaurar el botón
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonText;
        }
    });
});
