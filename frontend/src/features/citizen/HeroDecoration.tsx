import "./HeroDecoration.css";

export type HeroArtStyle = "flowing_lines" | "architectural" | "none";

type HeroDecorationProps = {
  style: HeroArtStyle;
};

export function HeroDecoration({ style }: HeroDecorationProps) {
  if (style === "none") return null;

  return (
    <div
      className={`citizen-hero-decoration citizen-hero-decoration--${style}`}
      aria-hidden="true"
    >
      {style === "flowing_lines" ? (
        <svg viewBox="0 0 1200 500" preserveAspectRatio="none" focusable="false">
          <path className="decoration-line decoration-line-primary" d="M-24 463 C160 421 245 489 430 454 S692 410 830 445 C973 480 1050 468 1224 414" />
          <path className="decoration-line decoration-line-accent" d="M-18 485 C154 447 269 499 445 474 S690 433 830 466 C970 493 1074 483 1216 440" />
          <path className="decoration-line decoration-line-light" d="M-16 440 C153 407 254 469 424 435 S681 397 816 428 C947 459 1072 449 1214 397" />
          <path className="decoration-line decoration-line-accent-short" d="M705 499 C826 468 891 479 1001 455 S1133 427 1214 403" />
          <circle className="decoration-node" cx="430" cy="454" r="4" />
          <circle className="decoration-node decoration-node-secondary" cx="830" cy="445" r="3" />
        </svg>
      ) : (
        <svg viewBox="0 0 1200 500" preserveAspectRatio="none" focusable="false">
          <path className="decoration-line decoration-line-primary" d="M-16 468 H390 V456 H608 V444 H812 V432 H1015 V420 H1218" />
          <path className="decoration-line decoration-line-accent" d="M-16 489 H372 V477 H590 V465 H794 V453 H997 V441 H1218" />
          <path className="decoration-line decoration-line-light" d="M-16 446 H410 V434 H628 V422 H832 V410 H1035 V398 H1218" />
          <path className="decoration-line decoration-line-accent-short" d="M798 499 V485 H958 V473 H1091 V461 H1218" />
          <path className="decoration-line decoration-line-primary" d="M1048 499 V483 H1110 V471 H1170 V459" />
          <circle className="decoration-node" cx="812" cy="432" r="4" />
          <circle className="decoration-node decoration-node-secondary" cx="1015" cy="420" r="3" />
        </svg>
      )}
    </div>
  );
}
