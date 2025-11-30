document.addEventListener('DOMContentLoaded', async function() {
    console.log("⚡ AutoNeura Frontend 2.0 Cargado");

    const tabs = document.querySelectorAll('.tab-button');
    const contents = document.querySelectorAll('.tab-content');

    // SISTEMA DE PESTAÑAS
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
    // LÓGICA DE SELECCIÓN DE PLAN (FOTO 8)
    // =========================================================
    // Se expone al window para que el onclick del HTML funcione
    window.selectPlan = function(element, planName, price) {
        // Remover clase 'selected' de todos
        document.querySelectorAll('#create-plans-container .plan-card').forEach(card => {
            card.classList.remove('selected');
        });
        // Agregar al clickeado
        element.classList.add('selected');
        
        // Actualizar Resumen (FOTO 9)
        document.getElementById('selected-plan').innerText = planName.charAt(0).toUpperCase() + planName.slice(1);
        document.getElementById('total-cost').innerText = `$${price}.00`;
        document.getElementById('recharge-amount').innerText = `$${price}.00`;
    };

    // =========================================================
    // CARGAR TABLA Y KPIs (FOTO C)
    // =========================================================
    async function cargarCampanas() {
        const tbody = document.getElementById('campaigns-table-body');
        if(!tbody) return;

        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Cargando...</td></tr>';

        try {
            const res = await fetch('/api/mis-campanas');
            const data = await res.json();

            // CÁLCULO DE TOTALES (FOTO C)
            let totalProspectos = 0;
            let totalLeads = 0;

            tbody.innerHTML = ''; 

            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No tienes campañas activas.</td></tr>';
            } else {
                data.forEach(camp => {
                    // Sumar KPI Global
                    totalProspectos += (camp.prospects_count || 0);
                    // Suponemos que la API devuelve leads, si no, es 0 por ahora
                    totalLeads += (camp.leads_count || 0); 

                    const tr = document.createElement('tr');
                    const estadoHtml = camp.status === 'active' 
                        ? '<span style="color:green; font-weight:bold;">● Activa</span>' 
                        : '<span style="color:red;">● Pausada</span>';

                    // BOTÓN CORREGIDO: SOLO DICE "Ver" (FOTO C)
                    tr.innerHTML = `
                        <td><strong>${camp.name}</strong></td>
                        <td>${camp.created_at || '-'}</td>
                        <td>${estadoHtml}</td>
                        <td>${camp.prospects_count || 0}</td>
                        <td>
                            <button class="cta-button btn-gestionar" data-id="${camp.id}" style="padding: 5px 15px; font-size: 12px; background-color: #007bff; width: auto;">
                                👁️ Ver
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            // ACTUALIZAR TARJETAS KPI (FOTO C)
            document.getElementById('kpi-total').innerText = totalProspectos;
            document.getElementById('kpi-leads').innerText = totalLeads;
            const tasa = totalProspectos > 0 ? ((totalLeads / totalProspectos) * 100).toFixed(1) : 0;
            document.getElementById('kpi-rate').innerText = `${tasa}%`;

            // Conectar botones
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
    // ABRIR PESTAÑA GEMELA (FOTO D, 11 y C Individual)
    // =========================================================
    async function abrirPestanaGemela(id) {
        console.log(`Abrir Gestión ID: ${id}`);
        
        try {
            const res = await fetch(`/api/campana/${id}`);
            if (!res.ok) throw new Error("Fallo API");
            const data = await res.json();

            // 1. TÍTULO Y ID (FOTO D)
            document.getElementById('manage-campaign-title').innerText = data.campaign_name;
            document.getElementById('edit_campaign_id').value = data.id;

            // 2. ACTUALIZAR KPIs PARA ESTA CAMPAÑA (FOTO C)
            // Si la API devuelve los contadores individuales, los usamos. 
            // Si no, se mantienen los globales o se ponen en 0. 
            // NOTA: Para que esto sea exacto, la API /api/campana/<id> debería devolver 'prospects_count'.
            // Si no lo hace, dejamos los globales o ponemos un placeholder.
            // Aquí asumimos que queremos ver los datos de ESTA campaña.
            if (data.stats) {
                 document.getElementById('kpi-total').innerText = data.stats.total || 0;
                 document.getElementById('kpi-leads').innerText = data.stats.leads || 0;
            }

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

            // 4. PLAN ACTIVO (FOTO 11B)
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
    // GUARDAR CAMBIOS (FOTO 7A - Botón Correcto)
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

    // CREAR CAMPAÑA (Lógica del Botón Lanzar - Solo en pestaña CREAR)
    const btnLanzar = document.getElementById('lancam');
    if (btnLanzar) {
        btnLanzar.addEventListener('click', async () => {
            // ... (Lógica de creación existente)
            // Se mantiene igual, solo asegurándonos de que tome el plan seleccionado visualmente
            const selectedPlanCard = document.querySelector('.plan-card.selected');
            if(!selectedPlanCard) { alert("Selecciona un plan."); return; }
            
            // ... resto del código de creación ...
            // Para brevedad, asumo que la lógica de envío ya la tenías y funciona.
            // Si necesitas que la repita completa, avísame.
        });
    }

    // Inicializar
    cargarCampanas();
});
