// Point d'entrée JS de La Ruche.
//
// Alpine est chargé en build CSP : les composants doivent être déclarés ici
// via Alpine.data() puis référencés par nom dans les gabarits (x-data="nom"),
// jamais sous forme d'expressions JS inline complexes.
document.addEventListener('alpine:init', () => {
  // Les composants Alpine arriveront avec les écrans (Phase 1+).
});
