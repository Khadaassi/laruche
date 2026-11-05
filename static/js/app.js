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

// Cases à cocher des tâches : l'état change tout de suite côté client
// (optimiste) et HTMX le confirme. Si le serveur refuse ou ne répond pas,
// on remet la case dans son état précédent.
function revertTaskCheckbox(event) {
  const form = event.detail.elt;
  if (!form || !form.matches('[data-task-form]')) return;
  const checkbox = form.querySelector('input[type="checkbox"]');
  if (checkbox) checkbox.checked = !checkbox.checked;
}
document.addEventListener('htmx:responseError', revertTaskCheckbox);
document.addEventListener('htmx:sendError', revertTaskCheckbox);

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
