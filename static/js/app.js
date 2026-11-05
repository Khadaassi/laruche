// Point d'entrée JS de La Ruche.
//
// Alpine est chargé en build CSP : les composants doivent être déclarés ici
// via Alpine.data() puis référencés par nom dans les gabarits (x-data="nom"),
// jamais sous forme d'expressions JS inline complexes.
document.addEventListener('alpine:init', () => {
  // Écran partagé : recharge la page au changement de période (matin → midi…).
  // Un seul rechargement programmé, pas de sondage régulier : la base Neon
  // peut s'endormir entre deux périodes (quota de calcul).
  Alpine.data('periodClock', () => ({
    init() {
      const seconds = Number(this.$el.dataset.reloadIn);
      if (seconds > 0) {
        // Petite marge pour tomber après la borne côté serveur.
        setTimeout(() => window.location.reload(), (seconds + 5) * 1000);
      }
    },
  }));

  // Roue du samedi : le serveur a déjà tiré. On anime la rotation vers le
  // résultat, puis on le révèle (avec confettis, en CSS). En mouvement réduit
  // (système ou data-motion="reduced"), la roue est posée directement sur le
  // résultat, sans animation.
  Alpine.data('wheel', () => ({
    done: false,
    init() {
      const rotor = this.$refs.rotor;
      const turn = `rotate(${Number(rotor.dataset.rotation) || 0}deg)`;
      const reduced =
        window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
        document.documentElement.dataset.motion === 'reduced';
      if (reduced) {
        rotor.style.transform = turn;
        this.done = true;
        return;
      }
      rotor.addEventListener('transitionend', () => { this.done = true; }, { once: true });
      // Deux frames : l'état initial est peint avant de lancer la transition.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        rotor.classList.add('is-spinning');
        rotor.style.transform = turn;
      }));
      // Filet de sécurité si transitionend ne se déclenche pas (onglet masqué…).
      setTimeout(() => { this.done = true; }, 4500);
    },
  }));

  // « Journée terminée ! » en plein écran : l'animation est en CSS (jouée une fois).
  // Ici : focus sur « Super ! », fermeture au clic, à Échap, ou seule après 8 s
  // (un écran partagé ne doit pas rester bloqué si personne ne ferme).
  Alpine.data('celebrationOverlay', () => ({
    open: true,
    init() {
      this.$nextTick(() => this.$refs.close && this.$refs.close.focus({ preventScroll: true }));
      this.timer = setTimeout(() => this.close(), 10000);
      playFanfare(this.$el.dataset.sound);
    },
    close() {
      clearTimeout(this.timer);
      this.open = false;
    },
  }));

  // Minuteur FlyLady (15 min) : démarrer / pause / remise à zéro, petite fanfare à la fin.
  Alpine.data('minuteur', () => ({
    total: 0,
    left: 0,
    running: false,
    endAt: 0,
    init() {
      this.total = Number(this.$el.dataset.seconds) || 900;
      this.left = this.total;
      // Retour dans l'appli : le navigateur a pu ralentir le minuteur, on recalcule.
      document.addEventListener('visibilitychange', () => this.sync());
    },
    get display() {
      const m = Math.floor(this.left / 60);
      const s = this.left % 60;
      return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    },
    get label() {
      if (this.running) return 'Pause';
      if (this.left === 0) return 'Terminé, bravo !';
      return this.left === this.total ? 'Lancer 15 minutes' : 'Reprendre';
    },
    // Temps restant = heure de fin − maintenant (jamais « une seconde de moins par tic »).
    sync() {
      if (!this.running) return;
      this.left = Math.max(0, Math.ceil((this.endAt - Date.now()) / 1000));
      if (this.left === 0) {
        this.running = false;
        clearInterval(this.tick);
        playFanfare('day');
      }
    },
    toggle() {
      if (this.left === 0) return;
      if (this.running) {
        this.sync();
        this.running = false;
        clearInterval(this.tick);
        return;
      }
      this.running = true;
      this.endAt = Date.now() + this.left * 1000;
      this.tick = setInterval(() => this.sync(), 500);
    },
    reset() {
      clearInterval(this.tick);
      this.running = false;
      this.left = this.total;
    },
  }));

  // Notifications push de cet appareil (réglages parent). Le jeton CSRF vient de
  // l'attribut hx-headers du <body> (cookie HttpOnly, jamais lu en JS).
  Alpine.data('pushSettings', () => ({
    supported: false,
    enabled: false,
    denied: false,
    busy: false,
    message: 'Vérification…',
    urls: {},
    publicKey: '',
    get canEnable() { return this.supported && !this.enabled && !this.denied && !this.busy; },
    async init() {
      // Lu ici une fois : dans un clic, `this.$el` désigne le bouton, pas la section.
      const data = this.$el.dataset;
      this.publicKey = data.publicKey;
      this.urls = { subscribe: data.subscribeUrl, unsubscribe: data.unsubscribeUrl, test: data.testUrl };
      this.supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
      if (!this.supported) {
        this.message = isIos()
          ? 'Sur iPhone : ajoutez La Ruche à l\'écran d\'accueil (Partager → « Sur l\'écran d\'accueil »), ouvrez-la depuis l\'icône, puis revenez ici.'
          : 'Ce navigateur ne gère pas les notifications. Essayez avec Chrome ou l\'appli installée.';
        return;
      }
      this.denied = Notification.permission === 'denied';
      try {
        const registration = await this.registration();
        this.enabled = Boolean(await registration.pushManager.getSubscription());
        this.refresh();
      } catch (error) {
        this.message = 'Impossible de préparer les notifications sur cet appareil (' + error.message + ').';
      }
    },
    // Le service worker peut ne pas être encore enregistré : on l'enregistre, avec un délai maximal.
    async registration() {
      await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('service worker indisponible')), 10000));
      return Promise.race([navigator.serviceWorker.ready, timeout]);
    },
    refresh() {
      if (this.denied) this.message = 'Notifications bloquées : autorisez-les dans les réglages du navigateur (ou de l\'appli), puis rechargez la page.';
      else this.message = this.enabled ? 'Notifications activées sur cet appareil.' : 'Notifications désactivées sur cet appareil.';
    },
    csrf() {
      try { return JSON.parse(document.body.getAttribute('hx-headers'))['X-CSRFToken']; } catch (error) { return ''; }
    },
    post(url, body) {
      return fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrf() },
        body: JSON.stringify(body || {}),
      });
    },
    async enable() {
      this.busy = true;
      this.message = 'Activation…';
      try {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') { this.denied = permission === 'denied'; this.refresh(); return; }
        const registration = await this.registration();
        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
          const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('le service de notifications ne répond pas, réessayez')), 20000));
          subscription = await Promise.race([
            registration.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: base64UrlToBytes(this.publicKey),
            }),
            timeout,
          ]);
        }
        const response = await this.post(this.urls.subscribe, subscription.toJSON());
        if (!response.ok) throw new Error('serveur ' + response.status);
        this.enabled = true;
        this.message = 'Notifications activées sur cet appareil. Essayez « Envoyer un test ».';
      } catch (error) {
        this.message = 'L\'activation a échoué (' + error.message + ').';
      } finally {
        this.busy = false;
      }
    },
    async disable() {
      try {
        const registration = await this.registration();
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
          await this.post(this.urls.unsubscribe, { endpoint: subscription.endpoint });
          await subscription.unsubscribe();
        }
        this.enabled = false;
        this.refresh();
      } catch (error) {
        this.message = 'La désactivation a échoué (' + error.message + ').';
      }
    },
    async sendTest() {
      this.message = 'Envoi du test…';
      try {
        const response = await this.post(this.urls.test);
        const data = response.ok ? await response.json() : { delivered: 0 };
        this.message = data.delivered
          ? 'Test envoyé : il doit arriver dans quelques secondes.'
          : 'Le test n\'a pas pu être envoyé (réactivez les notifications ici).';
      } catch (error) {
        this.message = 'Le test a échoué (' + error.message + ').';
      }
    },
  }));

  // Compteur d'étoiles qui monte (ex. 11 → 12) après l'arrivée de l'étoile.
  // Mouvement réduit : la valeur finale reste affichée telle quelle.
  Alpine.data('countUp', () => ({
    init() {
      const from = Number(this.$el.dataset.from);
      const to = Number(this.$el.dataset.to);
      if (reducedMotion() || !(to > from)) return;
      this.$el.textContent = String(from);
      setTimeout(() => {
        this.$el.textContent = String(to);
        this.$el.classList.add('is-counting');
      }, 1500);
    },
  }));
});

// Cases à cocher (et petits pas chiffrés) : l'état change tout de suite côté client
// (optimiste) et HTMX l'enregistre. `hx-sync="this:queue last"` sur ces formulaires :
// des clics rapprochés n'envoient que le dernier état. En cas d'échec (réseau ou
// serveur), la case revient à son état précédent et un message propose de réessayer.
let failedForm = null;

function saveError() { return document.getElementById('save-error'); }

function showSaveError(form) {
  failedForm = form;
  const box = saveError();
  if (box) { box.classList.remove('hidden'); box.classList.add('flex'); }
}

function hideSaveError() {
  failedForm = null;
  const box = saveError();
  if (box) { box.classList.add('hidden'); box.classList.remove('flex'); }
}

document.addEventListener('htmx:beforeRequest', (event) => {
  const form = event.detail.elt;
  if (!form || !form.matches || !form.matches('form[hx-post]')) return;
  const checkbox = form.querySelector('input[type="checkbox"]');
  if (checkbox) form.dataset.wanted = checkbox.checked ? 'on' : 'off';
});

function onSaveFailure(event) {
  const form = event.detail.elt;
  if (!form || !form.matches || !form.matches('form[hx-post]')) return;
  const checkbox = form.querySelector('input[type="checkbox"]');
  if (checkbox && form.dataset.wanted) checkbox.checked = form.dataset.wanted !== 'on';
  showSaveError(form);
}
document.addEventListener('htmx:responseError', onSaveFailure);
document.addEventListener('htmx:sendError', onSaveFailure);
document.addEventListener('htmx:timeout', onSaveFailure);

document.addEventListener('htmx:afterRequest', (event) => {
  if (event.detail.successful && event.detail.elt === failedForm) hideSaveError();
});

document.addEventListener('click', (event) => {
  if (event.target.closest('[data-save-dismiss]')) hideSaveError();
  if (event.target.closest('[data-save-retry]') && failedForm) {
    const form = failedForm;
    const checkbox = form.querySelector('input[type="checkbox"]');
    if (checkbox && form.dataset.wanted) checkbox.checked = form.dataset.wanted === 'on';
    if (window.htmx) window.htmx.trigger(form, 'change');
  }
});

// Mouvement réduit : préférence système ou interrupteur (data-motion="reduced").
function reducedMotion() {
  return (
    document.documentElement.dataset.motion === 'reduced' ||
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

// Petite fanfare synthétisée (Web Audio, aucun fichier ni CDN) pour les vraies
// célébrations. Jouée juste après un tap (autorisé par les navigateurs). Coupée en
// mouvement réduit et si la tablette refuse le son : jamais d'erreur visible.
const FANFARES = {
  day: [523.25, 659.25, 783.99, 1046.5],
  tier: [392.0, 523.25, 659.25, 783.99, 1046.5, 1318.5],
};
function playFanfare(kind) {
  const notes = FANFARES[kind];
  if (!notes || reducedMotion()) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const start = ctx.currentTime + 0.25;
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const at = start + i * 0.13;
      const last = i === notes.length - 1;
      osc.type = 'triangle';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.18, at + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + (last ? 0.9 : 0.25));
      osc.connect(gain).connect(ctx.destination);
      osc.start(at);
      osc.stop(at + (last ? 1 : 0.3));
    });
    setTimeout(() => ctx.close(), 3000);
  } catch (error) {
    // Son indisponible : la célébration visuelle suffit.
  }
}

// Appli installable : enregistre le service worker (cache des fichiers statiques,
// page hors connexion, notifications). Sans effet si le navigateur ne le gère pas.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
  });
}

// Clé publique VAPID (base64url) → octets pour pushManager.subscribe.
function base64UrlToBytes(value) {
  const padded = (value + '='.repeat((4 - (value.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

function isIos() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}
