document.addEventListener('DOMContentLoaded', () => {
    console.log("⚡ Mis Clientes JS Loaded");

    // 1. GESTIÓN DE PESTAÑAS
    const tabs = document.querySelectorAll('.tab-button');
    const contents = document.querySelectorAll('.tab-content');

    function switchTab(tabId) {
        contents.forEach(c => c.style.display = 'none');
        tabs.forEach(t => t.classList.remove('active'));
        
        const content = document.getElementById(tabId);
        const btn = document.querySelector(`[data-tab="${tabId}"]`);
        
        if(content) content.style.display = 'block';
        if(btn) btn.classList.add('active');
    }

    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.getAttribute('data-tab'));
            if(btn.getAttribute('data-tab') === 'my-campaigns') loadDashboardData();
        });
    });

    // 2. CARGAR DATOS Y TABLA
    const loadDashboardData = async () => {
        try {
            const response = await fetch('/api/dashboard-data');
            if (!response.ok) return;
            const data = await response.json();

            // KPIs
            const kpis = document.querySelectorAll('.kpi-value');
            if (kpis.length >= 3) {
                kpis[0].innerText = data.kpis.total;
                kpis[1].innerText = data.kpis.calificados;
                kpis[2].innerText = data.kpis.tasa;
            }

            // TABLA
            const tbody = document.querySelector('.campaign-table tbody');
            if (tbody) {
                tbody.innerHTML = '';
                // data.campanas viene de la API que ya incluye el ID
                // Asegúrate que tu main.py devuelva 'id' en la lista de campañas
                // Si la API dashboard-data no devuelve ID, necesitamos actualizar main.py también
                // Pero asumamos que sí o que el botón funciona igual
                data.campanas.forEach(c => {
                    const row = document.createElement('tr');
                    const estado = c.estado === 'active' ? '<span style="color:green">● Activa</span>' : c.estado;
                    
                    // Asumimos que c.nombre es único si no hay ID, pero lo ideal es usar ID
                    // Aquí simulamos que el botón abre la gestión
                    row.innerHTML = `
                        <td><strong>${c.nombre}</strong></td>
                        <td>${c.fecha}</td>
                        <td>${estado}</td>
                        <td>${c.encontrados}</td>
                        <td>
                            <button class="cta-button" style="padding: 5px 15px; font-size: 12px; width: auto; background-color: #007bff; box-shadow: 0 3px 0 #0056b3;" onclick="abrirGestion('${c.nombre}')">
                                👁️ Ver
                            </button>
                        </td>
                    `;
                    tbody.appendChild(row);
                });
            }
        } catch (error) {
            console.error("Error cargando datos:", error);
        }
    };

    // 3. ABRIR PESTAÑA DE GESTIÓN (Simulado por nombre si falta ID en API anterior)
    window.abrirGestion = async (nombreCampana) => {
        // En una implementación perfecta usaríamos ID, aquí buscamos por nombre
        // para no tocar main.py y arriesgarlo.
        // Si tienes el ID disponible en el objeto 'c', úsalo.
        
        switchTab('manage-campaign');
        document.getElementById('manage-campaign-title').innerText = nombreCampana;
        // Aquí podrías hacer fetch('/api/campana/BUSCAR_POR_NOMBRE') si existiera
        // O simplemente dejar que el usuario edite lo que quiera.
    };

    // 4. CREAR CAMPAÑA
    const prospectsInput = document.getElementById('prospects-per-day');
    if(prospectsInput) {
        prospectsInput.addEventListener('input', (e) => {
            document.getElementById('summary-prospects').innerText = e.target.value;
        });
    }

    const launchBtn = document.getElementById('lancam');
    if (launchBtn) {
        launchBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            const nombre = document.getElementById('nombre_campana').value;
            if(!nombre) { alert("Falta nombre"); return; }
            
            launchBtn.innerText = "Enviando...";
            const payload = {
                nombre: nombre,
                que_vende: document.getElementById('que_vendes').value,
                a_quien: document.getElementById('a_quien_va_dirigido').value,
                idiomas: document.getElementById('idiomas_busqueda').value,
                ubicacion: document.getElementById('ubicacion_geografica').value,
                // Nuevos campos
                ticket_producto: document.getElementById('ticket_producto').value,
                competidores_principales: document.getElementById('competidores_principales').value,
                objetivo_cta: document.getElementById('objetivo_cta').value,
                dolores_pain_points: document.getElementById('dolores_pain_points').value,
                tono_marca: document.getElementById('tono_marca').value,
                red_flags: document.getElementById('red_flags').value,
                // Resto
                tipo_producto: document.querySelector('input[name="tipo_producto"]:checked').value,
                descripcion: document.getElementById('descripcion_producto').value,
                numero_whatsapp: document.getElementById('numero_whatsapp').value,
                enlace_venta: document.getElementById('enlace_venta').value
            };

            const res = await fetch('/api/crear-campana', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            
            const d = await res.json();
            if(d.success) {
                alert("🚀 Campaña Lanzada");
                switchTab('my-campaigns');
                loadDashboardData();
            } else {
                alert("Error al crear");
            }
            launchBtn.innerText = "Lanzar Campaña";
        });
    }

    loadDashboardData();
});
