document.addEventListener('DOMContentLoaded', async function() {
    console.log("🚀 Mis Clientes (Admin) Cargado");

    // =========================================================
    // 1. CONFIGURACIÓN DE BANDERAS (International Phone Input)
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

    // Aplicar a "Crear Campaña"
    const inputCreate = document.querySelector("#numero_whatsapp");
    if(inputCreate) window.intlTelInput(inputCreate, phoneInputOptions);

    // Aplicar a "Gestionar Campaña"
    const inputEdit = document.querySelector("#edit_numero_whatsapp");
    if(inputEdit) window.intlTelInput(inputEdit, phoneInputOptions);


    // =========================================================
    // 2. LÓGICA DE PESTAÑAS
    // =========================================================
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
    // 3. LÓGICA DEL CHATBOT (CEREBRO ARQUITECTO - ADMIN)
    // =========================================================
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');

    if (chatForm) {
        const newChatForm = chatForm.cloneNode(true);
        chatForm.parentNode.replaceChild(newChatForm, chatForm);
        
        const finalChatForm = document.getElementById('chat-form');
        const finalInput = document.getElementById('user-input');

        finalChatForm.addEventListener('submit', async (e) => {
            e.preventDefault(); // Evita el pestañeo
            
            const text = finalInput.value.trim();
            if (!text) return;

            // Mensaje Usuario
            const userMsgDiv = document.createElement('p');
            userMsgDiv.className = 'msg-user';
            userMsgDiv.textContent = text;
            chatMessages.appendChild(userMsgDiv);
            finalInput.value = '';

            // Loading
            const loadingDiv = document.createElement('p');
            loadingDiv.className = 'msg-assistant';
            loadingDiv.textContent = 'Analizando datos...';
            chatMessages.appendChild(loadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            try {
                const response = await fetch('/api/chat-arquitecto', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await response.json();
                loadingDiv.innerHTML = data.response.replace(/\n/g, '<br>');
            } catch (error) {
                loadingDiv.textContent = "Error de conexión.";
            }
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // =========================================================
    // 4. GESTIÓN DE CAMPAÑAS (CRUD)
    // =========================================================
    
    // CARGAR CAMPAÑAS
    async function cargarCampanas() {
        const tbody = document.getElementById('campaigns-table-body');
        if(!tbody) return;

        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Cargando...</td></tr>';

        try {
            const res = await fetch('/api/mis-campanas');
            const data = await res.json();

            let totalProspectos = 0;
            let totalLeads = 0;
            tbody.innerHTML = ''; 

            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hay campañas activas.</td></tr>';
            } else {
                data.forEach(camp => {
                    totalProspectos += (camp.prospects_count || 0);
                    // totalLeads += (camp.leads_count || 0); // Si tienes leads count

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
                                style="padding: 5px 15px; font-size: 12px; background-color: #007bff; width: auto; box-shadow: 0 3px 0 #0056b3;">
                                👁️ Ver
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            // Actualizar KPIs visuales
            const kpiTotal = document.getElementById('kpi-total');
            if(kpiTotal) kpiTotal.innerText = totalProspectos;

            // Listeners para botones "Ver"
            document.querySelectorAll('.btn-gestionar').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const id = e.target.getAttribute('data-id');
                    abrirPestanaGemela(id);
                });
            });

        } catch (error) {
            console.error("Error:", error);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:red;">Error de conexión.</td></tr>';
        }
    }

    // ABRIR EDICIÓN (Cargar datos en el formulario)
    async function abrirPestanaGemela(id) {
        try {
            const res = await fetch(`/api/campana/${id}`);
            if (!res.ok) throw new Error("Fallo API");
            const data = await res.json();

            // Llenar campos
            const title = document.getElementById('manage-campaign-title');
            if(title) title.innerText = data.campaign_name;
            
            const hiddenId = document.getElementById('edit_campaign_id');
            if(hiddenId) hiddenId.value = data.id;

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

            // Ir a la pestaña
            switchTab('manage-campaign');

        } catch (e) {
            alert("Error cargando campaña: " + e.message);
        }
    }

    // Helpers
    function setVal(id, val) { const el = document.getElementById(id); if(el) el.value = val || ''; }
    function setSelect(id, val) { const el = document.getElementById(id); if(el && val) el.value = val; }

    // BOTÓN ACTUALIZAR
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

                if(res.ok) alert("✅ Guardado correctamente.");
                else alert("❌ Error al guardar.");
            } catch (e) {
                alert("Error de red.");
            } finally {
                btnUpdate.innerText = "💾 Guardar Cambios";
                btnUpdate.disabled = false;
            }
        });
    }

    // BOTÓN CREAR (LANZAR)
    const btnLanzar = document.getElementById('lancam');
    if (btnLanzar) {
        btnLanzar.addEventListener('click', async () => {
            // Recolección de datos del formulario Crear
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
                ai_constitution: document.getElementById('ai_constitution') ? document.getElementById('ai_constitution').value : "",
                ai_blackboard: document.getElementById('ai_blackboard') ? document.getElementById('ai_blackboard').value : "",
                // Manejo seguro del radio button
                tipo_producto: document.querySelector('input[name="tipo_producto"]:checked') ? document.querySelector('input[name="tipo_producto"]:checked').value : "tangible",
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
                    cargarCampanas(); 
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

    // Carga inicial
    cargarCampanas();
});
