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
          <path className="decoration-line decoration-line-primary" d="M-24 433 C160 376 245 488 430 438 S692 352 830 411 C973 470 1050 453 1224 348" />
          <path className="decoration-line decoration-line-accent" d="M-18 462 C154 409 269 510 445 461 S690 389 830 443 C970 497 1074 474 1216 383" />
          <path className="decoration-line decoration-line-light" d="M-16 401 C153 349 254 455 424 408 S681 328 816 382 C947 434 1072 429 1214 315" />
          <path className="decoration-line decoration-line-accent-short" d="M705 499 C826 452 891 476 1001 438 S1133 393 1214 350" />
          <circle className="decoration-node" cx="430" cy="438" r="4" />
          <circle className="decoration-node decoration-node-secondary" cx="830" cy="411" r="3" />
        </svg>
      ) : (
        <svg viewBox="0 0 1200 500" preserveAspectRatio="none" focusable="false">
          <path className="decoration-line decoration-line-primary" d="M-16 470 H390 V425 H608 V385 H812 V345 H1015 V302 H1218" />
          <path className="decoration-line decoration-line-accent" d="M-16 489 H372 V444 H590 V404 H794 V364 H997 V321 H1218" />
          <path className="decoration-line decoration-line-light" d="M-16 447 H410 V402 H628 V362 H832 V322 H1035 V279 H1218" />
          <path className="decoration-line decoration-line-accent-short" d="M798 500 V457 H958 V417 H1091 V376 H1218" />
          <path className="decoration-line decoration-line-primary" d="M1048 500 V454 H1110 V412 H1170 V369" />
          <circle className="decoration-node" cx="812" cy="345" r="4" />
          <circle className="decoration-node decoration-node-secondary" cx="1015" cy="302" r="3" />
        </svg>
      )}
    </div>
  );
}
