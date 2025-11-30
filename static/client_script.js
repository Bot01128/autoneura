document.addEventListener('DOMContentLoaded', async function() {
    console.log("⚡ AutoNeura Frontend 2.0 Cargado");

    // =========================================================
    // 1. SISTEMA DE PESTAÑAS (TAB SYSTEM)
    // =========================================================
    const tabs = document.querySelectorAll('.tab-button');
    const contents = document.querySelectorAll('.tab-content');

    function switchTab(tabId) {
        // 1. Ocultar todo el contenido
        contents.forEach(content => content.style.display = 'none');
        
        // 2. Desactivar estilos de todos los botones
        tabs.forEach(tab => tab.classList.remove('active'));

        // 3. Mostrar el contenido seleccionado
        const selectedContent = document.getElementById(tabId);
        if (selectedContent) selectedContent.style.display = 'block';

        // 4. Activar el botón seleccionado
        const selectedTab = document.querySelector(`[data-tab="${tabId}"]`);
        if (selectedTab) selectedTab.classList.add('active');
        
        // NOTA: Ya no ocultamos el botón "Gestionar". Siempre está visible.
    }

    // Event Listeners para los botones del menú
    tabs.forEach(button => {
        button.addEventListener('click', () => {
            const target = button.getAttribute('data-tab');
            switchTab(target);
            // Si volvemos a "Mis Campañas", recargamos la tabla para ver cambios
            if (target === 'my-campaigns') cargarCampanas(); 
        });
    });

    // =========================================================
    // 2. CARGAR LISTA DE CAMPAÑAS (TABLA)
    // =========================================================
    async function cargarCampanas() {
        const tbody = document.getElementById('campaigns-table-body');
        if(!tbody) return;

        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Cargando...</td></tr>';

        try {
            const res = await fetch('/api/mis-campanas');
            const data = await res.json();

            tbody.innerHTML = ''; // Limpiar

            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No tienes campañas activas.</td></tr>';
                return;
            }

            data.forEach(camp => {
                const tr = document.createElement('tr');
                const estadoHtml = camp.status === 'active' 
                    ? '<span style="color:green; font-weight:bold;">● Activa</span>' 
                    : '<span style="color:red;">● Pausada</span>';

                tr.innerHTML = `
                    <td><strong>${camp.name}</strong></td>
                    <td>${camp.created_at || '-'}</td>
                    <td>${estadoHtml}</td>
                    <td>${camp.prospects_count || 0}</td>
                    <td>
                        <button class="cta-button btn-gestionar" data-id="${camp.id}" style="padding: 5px 15px; font-size: 12px; background-color: #007bff; width: auto;">
                            👁️ Ver / Editar
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });

            // Conectar los botones generados
            document.querySelectorAll('.btn-gestionar').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const id = e.target.getAttribute('data-id');
                    abrirPestanaGemela(id);
                });
            });

        } catch (error) {
            console.error("Error cargando campañas:", error);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:red;">Error de conexión.</td></tr>';
        }
    }

    // =========================================================
    // 3. ABRIR PESTAÑA GEMELA (CARGAR DATOS)
    // =========================================================
    async function abrirPestanaGemela(id) {
        console.log(`Abrir Gestión ID: ${id}`);
        
        try {
            const res = await fetch(`/api/campana/${id}`);
            if (!res.ok) throw new Error("Fallo API");
            const data = await res.json();

            // 1. Llenar los campos del formulario de edición (IDs del HTML nuevo)
            document.getElementById('manage-campaign-title').innerText = data.campaign_name;
            document.getElementById('edit_campaign_id').value = data.id;

            // Mapeo de datos DB -> HTML Inputs
            setVal('edit_nombre_campana', data.campaign_name);
            setVal('edit_que_vendes', data.product_description);
            setVal('edit_a_quien_va_dirigido', data.target_audience);
            setVal('edit_idiomas_busqueda', data.languages);
            setVal('edit_ticket_producto', data.ticket_price);
            setVal('edit_competidores_principales', data.competitors);
            setVal('edit_dolores_pain_points', data.pain_points_defined);
            setVal('edit_red_flags', data.red_flags);
            
            // CEREBRO
            setVal('edit_ai_constitution', data.adn_corporativo || ""); 
            setVal('edit_ai_blackboard', data.pizarron_contexto || "");
            
            // CONTACTO
            setVal('edit_numero_whatsapp', data.whatsapp_number);
            setVal('edit_enlace_venta', data.sales_link);

            // SELECTS
            setSelect('edit_objetivo_cta', data.cta_goal);
            setSelect('edit_tono_marca', data.tone_voice);

            // 2. Marcar el Plan Activo (Solo Visual)
            document.querySelectorAll('.plan-card').forEach(p => p.classList.remove('plan-active-readonly'));
            
            // Lógica simple para resaltar el plan
            let limit = data.daily_prospects_limit || 4;
            if (limit <= 4) document.getElementById('edit_plan_arrancador').classList.add('plan-active-readonly');
            else if (limit <= 15) document.getElementById('edit_plan_profesional').classList.add('plan-active-readonly');
            else document.getElementById('edit_plan_dominador').classList.add('plan-active-readonly');

            // 3. Ir a la pestaña
            switchTab('manage-campaign');

        } catch (e) {
            alert("No se pudo cargar la campaña: " + e.message);
        }
    }

    // Helpers
    function setVal(id, val) {
        const el = document.getElementById(id);
        if(el) el.value = val || '';
    }
    
    function setSelect(id, val) {
        const el = document.getElementById(id);
        if(el && val) el.value = val;
    }

    // =========================================================
    // 4. GUARDAR CAMBIOS (UPDATE)
    // =========================================================
    const btnUpdate = document.getElementById('btn-update-brain');
    if (btnUpdate) {
        btnUpdate.addEventListener('click', async () => {
            const id = document.getElementById('edit_campaign_id').value;
            if(!id) return;

            const payload = {
                id: id,
                campaign_name: document.getElementById('edit_nombre_campana').value,
                product_description: document.getElementById('edit_que_vendes').value,
                target_audience: document.getElementById('edit_a_quien_va_dirigido').value,
                languages: document.getElementById('edit_idiomas_busqueda').value,
                ticket_price: document.getElementById('edit_ticket_producto').value,
                cta_goal: document.getElementById('edit_objetivo_cta').value,
                competitors: document.getElementById('edit_competidores_principales').value,
                pain_points_defined: document.getElementById('edit_dolores_pain_points').value,
                red_flags: document.getElementById('edit_red_flags').value,
                tone_voice: document.getElementById('edit_tono_marca').value,
                adn_corporativo: document.getElementById('edit_ai_constitution').value,
                pizarron_contexto: document.getElementById('edit_ai_blackboard').value,
                whatsapp_number: document.getElementById('edit_numero_whatsapp').value,
                sales_link: document.getElementById('edit_enlace_venta').value
            };

            btnUpdate.innerText = "Guardando...";
            btnUpdate.disabled = true;

            try {
                const res = await fetch('/api/actualizar-campana', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });

                if(res.ok) {
                    alert("✅ Estrategia actualizada. Los bots leerán los nuevos datos.");
                } else {
                    alert("❌ Error al guardar.");
                }
            } catch (e) {
                alert("Error de red.");
            } finally {
                btnUpdate.innerText = "💾 Guardar Todos los Cambios";
                btnUpdate.disabled = false;
            }
        });
    }

    // =========================================================
    // 5. CREAR CAMPAÑA (LÓGICA FALTANTE)
    // =========================================================
    const btnLanzar = document.getElementById('lancam');
    if (btnLanzar) {
        btnLanzar.addEventListener('click', async () => {
            // Recolección de datos del formulario de CREAR
            const payload = {
                nombre: document.getElementById('nombre_campana').value,
                que_vende: document.getElementById('que_vendes').value,
                a_quien: document.getElementById('a_quien_va_dirigido').value,
                idiomas: document.getElementById('idiomas_busqueda').value,
                ubicacion: document.getElementById('ubicacion_geografica').value,
                ticket_producto: document.getElementById('ticket_producto').value,
                objetivo_cta: document.getElementById('objetivo_cta').value,
                competidores_principales: document.getElementById('competidores_principales').value,
                dolores_pain_points: document.getElementById('dolores_pain_points').value,
                red_flags: document.getElementById('red_flags').value,
                tono_marca: document.getElementById('tono_marca').value,
                ai_constitution: document.getElementById('ai_constitution').value,
                ai_blackboard: document.getElementById('ai_blackboard').value,
                tipo_producto: document.querySelector('input[name="tipo_producto"]:checked').value,
                numero_whatsapp: document.getElementById('numero_whatsapp').value,
                enlace_venta: document.getElementById('enlace_venta').value
            };

            // Validacion simple
            if(!payload.nombre || !payload.que_vende) {
                alert("Por favor completa al menos el Nombre y Qué Vendes.");
                return;
            }

            btnLanzar.innerText = "Lanzando...";
            btnLanzar.disabled = true;

            try {
                const res = await fetch('/api/crear-campana', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                
                const data = await res.json();

                if(data.success) {
                    alert("🚀 ¡Campaña Lanzada al Orquestador!");
                    // Volver a la lista
                    document.querySelector('[data-tab="my-campaigns"]').click();
                    // Limpiar formulario (opcional)
                    document.getElementById('nombre_campana').value = "";
                } else {
                    alert("Error: " + (data.error || "Desconocido"));
                }
            } catch (e) {
                alert("Error de conexión al crear campaña.");
            } finally {
                btnLanzar.innerText = "Lanzar Campaña al Orquestador";
                btnLanzar.disabled = false;
            }
        });
    }

    // Inicializar tabla al cargar
    cargarCampanas();
});
