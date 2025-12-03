document.addEventListener('DOMContentLoaded', async function() {
    console.log("⚡ AutoNeura Frontend 2.0 Cargado - Modo Inteligente Activo");

    // =========================================================
    // 0. INICIALIZAR BANDERAS DE PAÍSES (REPARACIÓN VISUAL)
    // =========================================================
    const phoneInputOptions = {
        initialCountry: "auto",
        geoIpLookup: function(callback) {
            fetch('https://ipapi.co/json')
                .then(function(res) { return res.json(); })
                .then(function(data) { callback(data.country_code); })
                .catch(function() { callback("us"); });
        },
        utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/utils.js"
    };

    const inputCreate = document.querySelector("#numero_whatsapp");
    if(inputCreate) window.intlTelInput(inputCreate, phoneInputOptions);

    const inputEdit = document.querySelector("#edit_numero_whatsapp");
    if(inputEdit) window.intlTelInput(inputEdit, phoneInputOptions);


    // Variable Global para controlar qué IA responde (Vendedora o Analista)
    let currentChatMode = 'analista'; // Por defecto

    // =========================================================
    // 1. LÓGICA DE PESTAÑAS
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
            switchTab(target);
            // Si entra a Mis Campañas, recargamos los datos por si hubo cambios
            if (target === 'my-campaigns') cargarCampanas(); 
        });
    });

    // =========================================================
    // 2. LÓGICA DE SELECCIÓN DE PLAN (VISUAL)
    // =========================================================
    // Esta función se llama desde el HTML onclick
    window.selectPlan = function(element, planName, price, prospects) {
        // Remover clase selected de todos
        document.querySelectorAll('#create-plans-container .plan-card').forEach(card => {
            card.classList.remove('selected');
        });
        // Agregar selected al clickeado
        element.classList.add('selected');
        
        // Actualizar el cuadro de Resumen Final
        document.getElementById('selected-plan').innerText = planName.charAt(0).toUpperCase() + planName.slice(1);
        document.getElementById('selected-prospects').innerText = prospects;
        document.getElementById('total-cost').innerText = `$${price}.00`;
        document.getElementById('recharge-amount').innerText = `$${price}.00`;
    };

    // =========================================================
    // 3. LÓGICA DEL CHATBOT HÍBRIDO (VENDEDOR / ANALISTA)
    // =========================================================
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');

    if (chatForm) {
        // Clonamos el formulario para asegurar limpieza de eventos
        const newChatForm = chatForm.cloneNode(true);
        chatForm.parentNode.replaceChild(newChatForm, chatForm);
        
        const finalChatForm = document.getElementById('chat-form');
        const finalInput = document.getElementById('user-input');

        finalChatForm.addEventListener('submit', async (e) => {
            e.preventDefault(); // EVITA RECARGA DE PÁGINA
            
            const text = finalInput.value.trim();
            if (!text) return;

            // 1. Mostrar mensaje del usuario en el chat
            const userMsgDiv = document.createElement('p');
            userMsgDiv.className = 'msg-user';
            userMsgDiv.textContent = text;
            chatMessages.appendChild(userMsgDiv);
            finalInput.value = '';

            // 2. Mostrar indicador de carga "Pensando..."
            const loadingDiv = document.createElement('p');
            loadingDiv.className = 'msg-assistant';
            loadingDiv.textContent = 'Procesando...';
            chatMessages.appendChild(loadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // 3. DECIDIR A QUÉ CEREBRO LLAMAR (Smart Switching)
            let endpoint = '';
            let payload = {};

            if (currentChatMode === 'vendedor') {
                // Si no tiene campañas, usa la IA Vendedora (Persuasiva)
                endpoint = '/chat'; 
                payload = { message: text };
            } else {
                // Si tiene campañas, usa la IA Analista (Supabase)
                endpoint = '/api/chat-arquitecto';
                payload = { message: text };
            }

            try {
                // Conexión con el Backend
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                // 4. Mostrar respuesta real
                loadingDiv.innerHTML = data.response.replace(/\n/g, '<br>');
            } catch (error) {
                console.error("Error chat:", error);
                loadingDiv.textContent = "Error: No puedo conectar con el servidor.";
            }
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // =========================================================
    // 4. LÓGICA DE GESTIÓN DE CAMPAÑAS (CARGA, INTERRUPTOR, ACTUALIZAR, LANZAR)
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

            // --- LÓGICA DEL INTERRUPTOR INTELIGENTE ---
            const advancedTabs = document.querySelectorAll('.advanced-feature');
            const assistantGreeting = document.querySelector('.msg-assistant');

            if (data.length === 0) {
                // CASO A: CLIENTE NUEVO (0 Campañas)
                // 1. Ocultar pestañas avanzadas
                advancedTabs.forEach(tab => tab.style.display = 'none');
                
                // 2. Cambiar Chat a MODO VENDEDOR
                currentChatMode = 'vendedor';
                if(assistantGreeting) {
                    assistantGreeting.innerHTML = "¡Hola! Veo que aún no tienes campañas activas.<br>Soy tu Asistente de Ventas. ¿Tienes dudas sobre cuál plan elegir?";
                }

                // 3. Forzar ir a la pestaña Crear Campaña si estamos en una oculta
                const activeTab = document.querySelector('.tab-button.active');
                if(!activeTab || activeTab.style.display === 'none'){
                    const createTab = document.querySelector('[data-tab="create-campaign"]');
                    if(createTab) createTab.click();
                }

                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No tienes campañas activas. ¡Crea la primera!</td></tr>';

            } else {
                // CASO B: CLIENTE ACTIVO (>0 Campañas)
                // 1. Mostrar pestañas avanzadas
                advancedTabs.forEach(tab => tab.style.display = 'inline-block');

                // 2. Cambiar Chat a MODO ANALISTA (Supabase)
                currentChatMode = 'analista';
                // No cambiamos el saludo dinámicamente aquí para no ser molestos si ya estaba chateando,
                // pero la lógica interna ya apunta al Arquitecto.

                // 3. Renderizar Tabla
                let totalProspectos = 0;
                let totalLeads = 0;
                tbody.innerHTML = ''; 

                data.forEach(camp => {
                    totalProspectos += (camp.prospects_count || 0);
                    totalLeads += (camp.leads_count || 0);

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

                // Re-activar listeners de botones "Ver"
                document.querySelectorAll('.btn-gestionar').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const id = e.target.getAttribute('data-id');
                        const p = parseInt(e.target.getAttribute('data-pros'));
                        const l = parseInt(e.target.getAttribute('data-leads'));
                        abrirPestanaGemela(id, p, l);
                    });
                });
            }

        } catch (error) {
            console.error("Error cargando campañas:", error);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:red;">Error de conexión.</td></tr>';
        }
    }

    // Actualiza los números grandes de arriba
    function actualizarKPIs(prospectos, leads) {
        document.getElementById('kpi-total').innerText = prospectos;
        document.getElementById('kpi-leads').innerText = leads;
        const tasa = prospectos > 0 ? ((leads / prospectos) * 100).toFixed(1) : 0;
        document.getElementById('kpi-rate').innerText = `${tasa}%`;
    }

    // Carga los datos en la pestaña "Gestionar"
    async function abrirPestanaGemela(id, prospectosLocales, leadsLocales) {
        actualizarKPIs(prospectosLocales, leadsLocales);
        try {
            const res = await fetch(`/api/campana/${id}`);
            if (!res.ok) throw new Error("Fallo API");
            const data = await res.json();

            // Llenar campos del formulario
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
            setVal('edit_numero_whatsapp', data.whatsapp_number);
            setVal('edit_enlace_venta', data.sales_link);
            setSelect('edit_objetivo_cta', data.cta_goal);
            setSelect('edit_tono_marca', data.tone_voice);

            // Resaltar plan actual
            document.querySelectorAll('.plan-disabled').forEach(p => p.classList.remove('plan-active-readonly'));
            let limit = data.daily_prospects_limit || 4;
            if (limit <= 4) document.getElementById('edit_plan_arrancador').classList.add('plan-active-readonly');
            else if (limit <= 15) document.getElementById('edit_plan_profesional').classList.add('plan-active-readonly');
            else document.getElementById('edit_plan_dominador').classList.add('plan-active-readonly');

            // Cambiar a la pestaña gestionar
            switchTab('manage-campaign');

        } catch (e) {
            alert("No se pudo cargar la campaña: " + e.message);
        }
    }

    // Funciones auxiliares para llenar inputs
    function setVal(id, val) { const el = document.getElementById(id); if(el) el.value = val || ''; }
    function setSelect(id, val) { const el = document.getElementById(id); if(el && val) el.value = val; }

    // BOTÓN GUARDAR CAMBIOS (Pestaña Gestionar)
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

    // BOTÓN LANZAR CAMPAÑA (Pestaña Crear)
    const btnLanzar = document.getElementById('lancam');
    if (btnLanzar) {
        btnLanzar.addEventListener('click', async () => {
            const selectedPlanCard = document.querySelector('.plan-card.selected');
            if(!selectedPlanCard) { alert("Por favor, selecciona un plan primero."); return; }
            
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
                    alert("🚀 ¡Campaña Lanzada con Éxito! El sistema comenzará a buscar prospectos.");
                    // Actualizar vista
                    document.querySelector('[data-tab="my-campaigns"]').click();
                    cargarCampanas(); 
                } else {
                    alert("Error: " + (data.error || "Error desconocido al crear campaña"));
                }
            } catch (e) {
                alert("Error de conexión al servidor.");
            } finally {
                btnLanzar.innerText = "Lanzar Campaña";
                btnLanzar.disabled = false;
            }
        });
    }

    // Iniciar carga al abrir la página
    cargarCampanas();
});
