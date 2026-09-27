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
