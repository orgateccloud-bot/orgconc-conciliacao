import { useEffect, useRef } from "react";

interface StarfieldProps {
  className?: string;
  density?: number;
  twinkleSpeed?: number;
}

/**
 * Campo de estrelas animado via canvas — decoracao reusavel para hero
 * sections premium (Login Aurora, splash, landing). aria-hidden por
 * padrao pois nao tem conteudo informativo.
 */
export function Starfield({
  className,
  density = 180,
  twinkleSpeed = 0.004,
}: StarfieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    type Star = { x: number; y: number; r: number; a: number; da: number };
    let stars: Star[] = [];
    let rafId: number;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    const init = () => {
      stars = Array.from({ length: density }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.2 + 0.3,
        a: Math.random(),
        da: (Math.random() - 0.5) * twinkleSpeed,
      }));
    };
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const s of stars) {
        s.a = Math.max(0.05, Math.min(1, s.a + s.da));
        if (s.a <= 0.05 || s.a >= 1) s.da *= -1;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(200,220,255,${s.a})`;
        ctx.fill();
      }
      rafId = requestAnimationFrame(draw);
    };

    const onResize = () => {
      resize();
      init();
    };

    resize();
    init();
    draw();
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
    };
  }, [density, twinkleSpeed]);

  return <canvas ref={canvasRef} aria-hidden className={className} />;
}
