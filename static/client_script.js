document.addEventListener('DOMContentLoaded', async function() {
    console.log("⚡ AutoNeura Frontend 2.0 Cargado - Modo Inteligente Activo");

    // =========================================================
    // 1. LÓGICA DE PESTAÑAS (YA NO EXISTE 'MANAGE-CAMPAIGN' COMO PESTAÑA)
    // =========================================================
    const tabs = document.querySelectorAll('.tab-button');
    const contents = document.querySelectorAll('.tab-content');

    function switchTab(tabId) {
        // Ocultar todos los contenidos
        contents.forEach(content => content.style.display = 'none');
        // Quitar clase active de todos los botones
        tabs.forEach(tab => tab.classList.remove('active'));

        // Mostrar contenido seleccionado
        const selectedContent = document.getElementById(tabId);
        if (selectedContent) selectedContent.style.display = 'block';

        // Activar botón seleccionado
        const selectedTab = document.querySelector(`[data-tab="${tabId}"]`);
        if (selectedTab) selectedTab.classList.add('active');
    }

    tabs.forEach(button => {
        button.addEventListener('click', () => {
            const target = button.getAttribute('data-tab');
            // Si el botón es "manage-campaign", lo redirigimos a "my-campaigns" porque ya no existe
            if(target === 'manage-campaign') {
                switchTab('my-campaigns');
            } else {
                switchTab(target);
            }
            // Si entra a Mis Campañas, recargamos los datos y cerramos edición
            if (target === 'my-campaigns') {
                cargarCampanas();
                if(typeof cerrarEdicion === 'function') cerrarEdicion(); 
            }
        });
    });

    // ... (Lógica de selección de plan se mantiene igual) ...
    window.selectPlan = function(element, planName, price, prospects) {
        document.querySelectorAll('#create-plans-container .plan-card').forEach(card => {
            card.classList.remove('selected');
        });
        element.classList.add('selected');
        document.getElementById('selected-plan').innerText = planName.charAt(0).toUpperCase() + planName.slice(1);
        document.getElementById('selected-prospects').innerText = prospects;
        document.getElementById('total-cost').innerText = `$${price}.00`;
        document.getElementById('recharge-amount').innerText = `$${price}.00`;
    };

    // ... (Chatbot Híbrido se mantiene igual) ...
    
    // =========================================================
    // 4. GESTIÓN DE CAMPAÑAS (MODIFICADA PARA VISTA UNIFICADA)
    // =========================================================
    let campañasCache = [];

    async function cargarCampanas() {
        const tbody = document.getElementById('campaigns-table-body');
        if(!tbody) return;

        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Cargando datos...</td></tr>';

        try {
            const res = await fetch('/api/mis-campanas');
            const data = await res.json();
            campañasCache = data;

            // --- Lógica del Interruptor Inteligente ---
            const advancedTabs = document.querySelectorAll('.advanced-feature');
            
            if (data.length === 0) {
                // CLIENTE NUEVO: Ocultar todo menos Crear
                advancedTabs.forEach(tab => tab.style.display = 'none');
                const activeTab = document.querySelector('.tab-button.active');
                if(!activeTab || activeTab.style.display === 'none'){
                    const createTab = document.querySelector('[data-tab="create-campaign"]');
                    if(createTab) createTab.click();
                }
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No tienes campañas activas. ¡Crea la primera!</td></tr>';
            } else {
                // CLIENTE VIEJO: Mostrar todo
                advancedTabs.forEach(tab => tab.style.display = 'inline-block');
                
                let totalProspectos = 0;
                let totalLeads = 0;
                tbody.innerHTML = ''; 

                data.forEach(camp => {
                    totalProspectos += (camp.prospects_count || 0);
                    // totalLeads += (camp.leads_count || 0);

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
                            <button class="cta-button btn-gestionar" 
                                data-id="${camp.id}" 
                                data-pros="${camp.prospects_count || 0}"
                                data-leads="${camp.leads_count || 0}"
                                style="padding: 5px 15px; font-size: 12px; background-color: #007bff; width: auto; box-shadow: 0 3px 0 #0056b3;">
                                👁️ Ver
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });

                actualizarKPIs(totalProspectos, totalLeads);

                // ACTIVAR BOTONES "VER" (DESPLIEGAN EL PANEL DE ABAJO)
                document.querySelectorAll('.btn-gestionar').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const id = e.target.getAttribute('data-id');
                        const p = parseInt(e.target.getAttribute('data-pros'));
                        const l = parseInt(e.target.getAttribute('data-leads'));
                        abrirEdicionEnMismaPagina(id, p, l); // <--- NUEVA FUNCIÓN
                    });
                });
            }

        } catch (error) {
            console.error("Error cargando campañas:", error);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:red;">Error de conexión.</td></tr>';
        }
    }

    function actualizarKPIs(prospectos, leads) {
        const tasa = prospectos > 0 ? ((leads / prospectos) * 100).toFixed(1) : 0;
        document.getElementById('kpi-total').innerText = prospectos;
        document.getElementById('kpi-leads').innerText = leads;
        document.getElementById('kpi-rate').innerText = `${tasa}%`;
    }

    // === NUEVA FUNCIÓN: MUESTRA EL FORMULARIO ABAJO ===
    async function abrirEdicionEnMismaPagina(id, prospectosLocales, leadsLocales) {
        // 1. Actualizar KPIs con los datos DE ESTA CAMPAÑA ESPECÍFICA
        actualizarKPIs(prospectosLocales, leadsLocales);
        
        try {
            const res = await fetch(`/api/campana/${id}`);
            if (!res.ok) throw new Error("Fallo API");
            const data = await res.json();

            // 2. Llenar formulario
            document.getElementById('manage-campaign-title').innerText = data.campaign_name;
            document.getElementById('edit_campaign_id').value = data.id;

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
            
            // Cargar WhatsApp en el plugin de banderas (si existe)
            const inputEdit = document.querySelector("#edit_numero_whatsapp");
            if(inputEdit && window.intlTelInputGlobals) {
                const iti = window.intlTelInputGlobals.getInstance(inputEdit);
                if(iti) iti.setNumber(data.whatsapp_number || "");
            } else {
                setVal('edit_numero_whatsapp', data.whatsapp_number);
            }

            setVal('edit_enlace_venta', data.sales_link);
            setSelect('edit_objetivo_cta', data.cta_goal);
            setSelect('edit_tono_marca', data.tone_voice);

            // 3. MOSTRAR EL PANEL DE EDICIÓN Y OCULTAR LA TABLA
            document.getElementById('campaigns-list-view').style.display = 'none';
            document.getElementById('edit-panel-container').style.display = 'block';
            
            // Scroll suave hacia arriba para ver los KPIs actualizados
            window.scrollTo({ top: 0, behavior: 'smooth' });

        } catch (e) {
            alert("No se pudo cargar la campaña: " + e.message);
        }
    }

    function setVal(id, val) { const el = document.getElementById(id); if(el) el.value = val || ''; }
    function setSelect(id, val) { const el = document.getElementById(id); if(el && val) el.value = val; }

    // BOTÓN GUARDAR CAMBIOS
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
                competidores: document.getElementById('edit_competidores_principales').value,
                pain_points_defined: document.getElementById('edit_dolores_pain_points').value,
                red_flags: document.getElementById('edit_red_flags').value,
                tone_voice: document.getElementById('edit_tono_marca').value,
                adn_corporativo: document.getElementById('edit_ai_constitution').value,
                pizarron_contexto: document.getElementById('edit_ai_blackboard').value,
                whatsapp_number: document.querySelector("#edit_numero_whatsapp").nextElementSibling.classList.contains("iti") 
                    ? window.intlTelInputGlobals.getInstance(document.querySelector("#edit_numero_whatsapp")).getNumber()
                    : document.getElementById('edit_numero_whatsapp').value,
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
                    alert("✅ Guardado.");
                    // Volver a la lista
                    if(typeof cerrarEdicion === 'function') cerrarEdicion();
                    cargarCampanas();
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

    // BOTÓN LANZAR CAMPAÑA (Igual que antes...)
    const btnLanzar = document.getElementById('lancam');
    if (btnLanzar) {
        btnLanzar.addEventListener('click', async () => {
            // ... (Tu código de lanzar campaña se mantiene igual) ...
            // (Para ahorrar espacio no lo repito aquí, pero asegúrate de pegarlo completo)
            // Si necesitas que te lo escriba de nuevo, dímelo.
            
            // ... [LÓGICA DEL BOTÓN LANZAR] ...
            
            // ALERTA: PEGA AQUÍ LA LÓGICA DE LANZAR CAMPAÑA QUE YA TENÍAS
            // O SI QUIERES EL ARCHIVO 100% COMPLETO SIN RECORTES, PÍDEMELO.
        });
    }

    // Iniciar carga al abrir la página
    cargarCampanas();
});
