// frontend/js/auth.js
// Lógica de login, registro y alternancia entre ambas vistas.

const vistaLogin = document.getElementById('vista-login');
const vistaRegistro = document.getElementById('vista-registro');

// --- Alternar entre login y registro ---
document.getElementById('link-a-registro').addEventListener('click', (e) => {
  e.preventDefault(); // evita que el link recargue la página
  vistaLogin.classList.add('oculto');
  vistaRegistro.classList.remove('oculto');
});

document.getElementById('link-a-login').addEventListener('click', (e) => {
  e.preventDefault();
  vistaRegistro.classList.add('oculto');
  vistaLogin.classList.remove('oculto');
});

// --- LOGIN ---
document.getElementById('form-login').addEventListener('submit', async (e) => {
  e.preventDefault(); // evita que el form recargue la página (comportamiento por defecto de HTML)

  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;
  const errorEl = document.getElementById('login-error');
  errorEl.textContent = '';

  try {
    const data = await apiPost(LOGIN_ENDPOINT, { email, password });
    guardarSesion(data);

    redirigirSegunRol(data.role);

  } catch (error) {
    errorEl.textContent = error.message; // ej: "Credenciales inválidas"
  }
});

// --- REGISTRO ---
document.getElementById('form-registro').addEventListener('submit', async (e) => {
  e.preventDefault();

  const body = {
    first_name: document.getElementById('reg-first-name').value,
    middle_name: document.getElementById('reg-middle-name').value || null,
    last_name: document.getElementById('reg-last-name').value,
    second_last_name: document.getElementById('reg-second-last-name').value || null,
    document_number: document.getElementById('reg-document').value,
    email: document.getElementById('reg-email').value,
    phone: document.getElementById('reg-phone').value || null,
    password: document.getElementById('reg-password').value,
  };

  const errorEl = document.getElementById('registro-error');
  const exitoEl = document.getElementById('registro-exito');
  errorEl.textContent = '';
  exitoEl.textContent = '';

  try {
    await apiPost('/auth/register', body);

    exitoEl.textContent = 'Cuenta creada. Ya podés iniciar sesión.';
    document.getElementById('form-registro').reset();

    // Después de 1.5s, lo mandamos de vuelta a la vista de login
    setTimeout(() => {
      vistaRegistro.classList.add('oculto');
      vistaLogin.classList.remove('oculto');
      exitoEl.textContent = '';
    }, 1500);

  } catch (error) {
    errorEl.textContent = error.message; // ej: "Ese correo ya está registrado"
  }
});

// --- Redirección post-login según rol ---
function redirigirSegunRol(role) {
  switch (role) {
    case 'client':
      window.location.href = 'pages/catalogo.html';
      break;
    case 'mechanic':
      window.location.href = 'pages/dashboard-empleado.html';
      break;
    case 'admin':
    case 'owner':
      window.location.href = 'pages/dashboard-admin.html';
      break;
    default:
      console.error('Rol desconocido:', role);
  }
}