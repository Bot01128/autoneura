document.addEventListener('DOMContentLoaded', function() {
    console.log("⚡ AutoNeura Frontend Cargado");

    // =========================================================
    // 1. GESTIÓN DE PESTAÑAS (Crear vs Gestionar)
    // =========================================================
    const tabCrear = document.getElementById('tab-crear');
    const tabGestionar = document.getElementById('tab-gestionar');
    const contentCrear = document.getElementById('content-crear');
    const contentGestionar = document.getElementById('content-gestionar');

    if (tabCrear && tabGestionar) {
        tabCrear.addEventListener('click', () => {
            cambiarPestana('crear');
        });
        
        tabGestionar.addEventListener('click', () => {
            // Si el usuario da clic manual, mostramos lista vacía o mensaje
            cambiarPestana('gestionar'); 
        });
    }

    function cambiarPestana(modo) {
        if (modo === 'crear') {
            tabCrear.classList.add('active', 'bg-blue-600', 'text-white');
            tabCrear.classList.remove('bg-gray-200', 'text-gray-700');
            tabGestionar.classList.remove('active', 'bg-yellow-500', 'text-white');
            tabGestionar.classList.add('bg-gray-200', 'text-gray-700');
            
            contentCrear.classList.remove('hidden');
            contentGestionar.classList.add('hidden');
        } else {
            tabGestionar.classList.add('active', 'bg-yellow-500', 'text-white');
            tabGestionar.classList.remove('bg-gray-200', 'text-gray-700');
            tabCrear.classList.remove('active', 'bg-blue-600', 'text-white');
            tabCrear.classList.add('bg-gray-200', 'text-gray-700');

            contentGestionar.classList.remove('hidden');
            contentCrear.classList.add('hidden');
        }
    }

    // =========================================================
    // 2. LOGICA DEL BOTÓN "GESTIONAR CAMPAÑA" (REPARACIÓN)
    // =========================================================
    
    // Detectamos clics en los botones de la lista de campañas
    document.querySelectorAll('.btn-gestionar-campana').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const campanaId = this.getAttribute('data-id');
            cargarDatosCampana(campanaId);
        });
    });

    async function cargarDatosCampana(id) {
        console.log(`📡 Cargando datos de campaña ID: ${id}...`);
        
        try {
            // Llamamos a la API del Backend (main.py debe tener esta ruta)
            const response = await fetch(`/api/campana/${id}`);
            if (!response.ok) throw new Error("Error al obtener datos");
            
            const data = await response.json();
            
            // 1. Cambiamos a la pestaña de Gestión automáticamente
            cambiarPestana('gestionar');

            // 2. Poblamos los campos (MODO LECTURA vs EDICIÓN)
            
            // ID Oculto para saber qué actualizamos
            document.getElementById('edit_campaign_id').value = data.id;

            // Datos Informativos (Solo Texto)
            document.getElementById('view_campaign_name').innerText = data.campaign_name;
            document.getElementById('view_status').innerHTML = data.status === 'active' 
                ? '<span class="text-green-600 font-bold">ACTIVA 🟢</span>' 
                : '<span class="text-red-600 font-bold">PAUSADA 🔴</span>';

            // CAMPOS EDITABLES (ADN y Estrategia)
            // Asegúrate de que estos IDs existan en tu HTML client_dashboard.html
            setVal('edit_product_description', data.product_description);
            setVal('edit_target_audience', data.target_audience);
            setVal('edit_mission_statement', data.mission_statement);
            setVal('edit_tone_voice', data.tone_voice);
            
            // CAMPOS NUEVOS (Pizarrón y Competencia)
            setVal('edit_competitors', data.competitors);
            setVal('edit_red_flags', data.red_flags);
            setVal('edit_pizarron', data.pizarron_contexto || ""); // El Pizarrón nuevo

            // PLAN CONTRATADO (SOLO LECTURA - BLOQUEADO)
            // Esto evita que cambien el plan sin pagar
            const planSelect = document.getElementById('view_plan_type');
            if(planSelect) {
                planSelect.value = data.product_type; // 'Tangible', 'Intangible'
                planSelect.disabled = true; // Bloqueado visualmente
            }
            
            const dailySelect = document.getElementById('view_daily_limit');
            if(dailySelect) {
                dailySelect.value = data.daily_prospects_limit;
                dailySelect.disabled = true; // Bloqueado visualmente
            }

            console.log("✅ Datos cargados correctamente en la Pestaña Gemela");

        } catch (error) {
            console.error("❌ Error cargando campaña:", error);
            alert("No se pudieron cargar los datos de la campaña. Revisa la consola.");
        }
    }

    // Helper para asignar valor si el input existe
    function setVal(id, valor) {
        const el = document.getElementById(id);
        if (el) el.value = valor || '';
    }

    // =========================================================
    // 3. GUARDAR CAMBIOS (BOTÓN ACTUALIZAR)
    // =========================================================
    const formEdicion = document.getElementById('form-editar-campana');
    if (formEdicion) {
        formEdicion.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const id = document.getElementById('edit_campaign_id').value;
            if (!id) return;

            const datosActualizados = {
                product_description: document.getElementById('edit_product_description').value,
                target_audience: document.getElementById('edit_target_audience').value,
                mission_statement: document.getElementById('edit_mission_statement').value,
                tone_voice: document.getElementById('edit_tone_voice').value,
                competitors: document.getElementById('edit_competitors').value,
                red_flags: document.getElementById('edit_red_flags').value,
                pizarron_contexto: document.getElementById('edit_pizarron').value
            };

            try {
                const res = await fetch('/api/actualizar-campana', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id: id, ...datosActualizados })
                });

                if (res.ok) {
                    alert("✅ Estrategia actualizada. Los bots leerán los nuevos datos.");
                } else {
                    alert("❌ Error al guardar.");
                }
            } catch (error) {
                console.error(error);
                alert("Error de conexión.");
            }
        });
    }
});
