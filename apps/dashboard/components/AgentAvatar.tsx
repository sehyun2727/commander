import { initials } from "@/lib/utils";

export function AgentAvatar({ name, color, size = 36 }: { name: string; color: string; size?: number }) {
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, backgroundColor: color, fontSize: Math.round(size * 0.38) }}
    >
      {initials(name)}
    </div>
  );
}
