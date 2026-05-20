import logoUrl from "@/assets/logo.png";

interface Props {
  size?: number;
  className?: string;
}

export function Logo({ size = 40, className = "" }: Props) {
  return (
    <img
      src={logoUrl}
      alt="ORGATEC"
      width={size}
      height={size}
      className={`object-contain ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
