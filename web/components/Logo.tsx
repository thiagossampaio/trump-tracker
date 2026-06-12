/**
 * Marca "Aberration Pulse" — linha de base (norma histórica da presidência)
 * interrompida por um pico anômalo, sobre Old Glory Blue com a faixa ledger
 * em Old Glory Red. Mesmo artwork de public/logo.svg, favicon e ícones PWA.
 */
export default function LogoMark({
  className = "size-9",
}: {
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 100 100"
      className={className}
      role="img"
      aria-hidden
      focusable="false"
    >
      <rect width="100" height="100" rx="22" fill="#0A3161" />
      <path
        d="M1.93 87H98.07A22 22 0 0 1 78 100H22A22 22 0 0 1 1.93 87Z"
        fill="#B31942"
      />
      <path
        d="M14 55H36L46 24L56 72L62 55H86"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
