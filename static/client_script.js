document.addEventListener('DOMContentLoaded', async function() {
    console.log("⚡ AutoNeura Frontend 2.0 Cargado");

    const tabs = document.querySelectorAll('.tab-button');
    const contents = document.querySelectorAll('.tab-content');

    function switchTab(tabId) {
        contents.forEach(content => content.style.display = 'none');
        tabs.forEach(tab => tab.classList.remove('active'));

        const selectedContent = document.getElementById(tabId);
        if (selectedContent) selectedContent.style.display = 'block';

        const selectedTab = document.querySelector(`[data-tab="${tabId}"]`);
        if (selectedTab) selectedTab.classList.add('active');
    }

    tabs.forEach(button => {
        button.addEventListener('click', () => {
            const target = button.getAttribute('data-tab');
            switchTab(target);
            if (target === 'my-campaigns') cargarCampanas(); 
        });
    });

    // =========================================================
    // LÓGICA DE SELECCIÓN DE PLAN (FOTO 2)
    // =========================================================
    window.selectPlan = function(element, planName, price) {
        document.querySelectorAll('#create-plans-container .plan-card').forEach(card => {
            card.classList.remove('selected');
        });
        element.classList.add('selected');
        
        // Actualizar Resumen (FOTO 7B)
        document.getElementById('selected-plan').innerText = planName.charAt(0).toUpperCase() + planName.slice(1);
        document.getElementById('total-cost').innerText = `$${price}.00`;
        document.getElementById('recharge-amount').innerText = `$${price}.00`;
    };

    // =========================================================
    // CARGAR TABLA Y KPIs (FOTO C)
    // =========================================================
    // Variable global para guardar datos y usarlos en los KPIs
    let campañasCache = [];

    async function cargarCampanas() {
        const tbody = document.getElementById('campaigns-table-body');
        if(!tbody) return;

        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Cargando...</td></tr>';

        try {
            const res = await fetch('/api/mis-campanas');
            const data = await res.json();
            campañasCache = data; // Guardar para uso local

            let totalProspectos = 0;
            let totalLeads = 0;

            tbody.innerHTML = ''; 

            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No tienes campañas activas.</td></tr>';
            } else {
                data.forEach(camp => {
                    totalProspectos += (camp.prospects_count || 0);
                    totalLeads += (camp.leads_count || 0);

                    const tr = document.createElement('tr');
                    const estadoHtml = camp.status === 'active' 
                        ? '<span style="color:green; font-weight:bold;">● Activa</span>' 
                        : '<span style="color:red;">● Pausada</span>';

                    // FOTO 11A: BOTÓN DICE "Ver" (y tiene atributos para KPIs)
                    tr.innerHTML = `
                        <td><strong>${camp.name}</strong></td>
                        <td>${camp.created_at || '-'}</td>
                        <td>${estadoHtml}</td>
                        <td>${camp.prospects_count || 0}</td>
                        <td>
                            <button class="cta-button btn-gestionar" 
                                data-id="${camp.id}" 
                                data-pros="${camp.prospects_count || 0}"
                                data-leads="${camp.leads_count || 0}"
                                style="padding: 5px 15px; font-size: 12px; background-color: #007bff; width: auto;">
                                👁️ Ver
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            // ACTUALIZAR KPIs GLOBALES (FOTO C)
            actualizarKPIs(totalProspectos, totalLeads);

            // CONECTAR BOTONES
            document.querySelectorAll('.btn-gestionar').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const id = e.target.getAttribute('data-id');
                    // Obtenemos los datos individuales del botón para actualizar KPIs al instante
                    const p = parseInt(e.target.getAttribute('data-pros'));
                    const l = parseInt(e.target.getAttribute('data-leads'));
                    
                    abrirPestanaGemela(id, p, l);
                });
            });

        } catch (error) {
            console.error("Error cargando campañas:", error);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:red;">Error de conexión.</td></tr>';
        }
    }

    function actualizarKPIs(prospectos, leads) {
        document.getElementById('kpi-total').innerText = prospectos;
        document.getElementById('kpi-leads').innerText = leads;
        const tasa = prospectos > 0 ? ((leads / prospectos) * 100).toFixed(1) : 0;
        document.getElementById('kpi-rate').innerText = `${tasa}%`;
    }

    // =========================================================
    // ABRIR PESTAÑA GEMELA
    // =========================================================
    async function abrirPestanaGemela(id, prospectosLocales, leadsLocales) {
        console.log(`Abrir Gestión ID: ${id}`);
        
        // 1. ACTUALIZAR KPIs CON DATOS INDIVIDUALES (FOTO C)
        actualizarKPIs(prospectosLocales, leadsLocales);

        try {
            const res = await fetch(`/api/campana/${id}`);
            if (!res.ok) throw new Error("Fallo API");
            const data = await res.json();

            // 2. TÍTULO Y ID (FOTO D)
            document.getElementById('manage-campaign-title').innerText = data.campaign_name;
            document.getElementById('edit_campaign_id').value = data.id;

            // 3. LLENAR FORMULARIO
            setVal('edit_nombre_campana', data.campaign_name);
            setVal('edit_que_vendes', data.product_description);
            setVal('edit_a_quien_va_dirigido', data.target_audience);
            setVal('edit_idiomas_busqueda', data.languages);
            setVal('edit_ticket_producto', data.ticket_price);
            setVal('edit_competidores_principales', data.competitors);
            setVal('edit_dolores_pain_points', data.pain_points_defined);
            setVal('edit_red_flags', data.red_flags);
            setVal('edit_ai_constitution', data.adn_corporativo || ""); 
            setVal('edit_ai_blackboard', data.pizarron_contexto || "");
            setVal('edit_numero_whatsapp', data.whatsapp_number);
            setVal('edit_enlace_venta', data.sales_link);
            setSelect('edit_objetivo_cta', data.cta_goal);
            setSelect('edit_tono_marca', data.tone_voice);

            // 4. PLAN ACTIVO (FOTO 1: Resaltar en Verde)
            document.querySelectorAll('.plan-card').forEach(p => p.classList.remove('plan-active-readonly'));
            let limit = data.daily_prospects_limit || 4;
            if (limit <= 4) document.getElementById('edit_plan_arrancador').classList.add('plan-active-readonly');
            else if (limit <= 15) document.getElementById('edit_plan_profesional').classList.add('plan-active-readonly');
            else document.getElementById('edit_plan_dominador').classList.add('plan-active-readonly');

            switchTab('manage-campaign');

        } catch (e) {
            alert("No se pudo cargar la campaña: " + e.message);
        }
    }

    function setVal(id, val) { const el = document.getElementById(id); if(el) el.value = val || ''; }
    function setSelect(id, val) { const el = document.getElementById(id); if(el && val) el.value = val; }

    // =========================================================
    // GUARDAR CAMBIOS
    // =========================================================
    const btnUpdate = document.getElementById('btn-update-brain');
    if (btnUpdate) {
        btnUpdate.addEventListener('click', async () => {
            const id = document.getElementById('edit_campaign_id').value;
            if(!id) return;

            // ... (Resto de lógica de guardado igual) ...
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
                    alert("✅ Cambios Guardados Exitosamente.");
                } else {
                    alert("❌ Error al guardar.");
                }
            } catch (e) {
                alert("Error de red.");
            } finally {
                btnUpdate.innerText = "💾 Guardar Cambios";
                btnUpdate.disabled = false;
            }
        });
    }

    // CREAR CAMPAÑA
    const btnLanzar = document.getElementById('lancam');
    if (btnLanzar) {
        btnLanzar.addEventListener('click', async () => {
            const selectedPlanCard = document.querySelector('.plan-card.selected');
            if(!selectedPlanCard) { alert("Selecciona un plan."); return; }
            
            // ... (Lógica de envío se mantiene igual) ...
            // Asumiendo que el resto del bloque no cambia, lo resumo para no cortar:
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
                    alert("🚀 ¡Campaña Lanzada!");
                    document.querySelector('[data-tab="my-campaigns"]').click();
                } else {
                    alert("Error: " + (data.error || "Desconocido"));
                }
            } catch (e) {
                alert("Error de conexión.");
            } finally {
                btnLanzar.innerText = "Lanzar Campaña";
                btnLanzar.disabled = false;
            }
        });
    }

    cargarCampanas();
});
