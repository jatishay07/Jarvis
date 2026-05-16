import { motion, AnimatePresence } from "motion/react";
import { useRef, useState, useEffect, useCallback } from "react";

// ── Config: map GitHub repo name → absolute local path ───────────────────────
// Add your repos here. Leave localPath null if no local copy.
const LOCAL_PATHS: Record<string, string | null> = {
  Jarvis: "/Users/Atishay/Documents/GitHub/LandingPage/Jarvis",
  // "CottageMP": "/Users/Atishay/Documents/GitHub/CottageMP",
  // Add more repos here...
};

// ── Types ─────────────────────────────────────────────────────────────────────
interface Repo {
  id: number;
  name: string;
  full_name: string;
  html_url: string;
  description: string | null;
}

interface ActionMenuState {
  repo: Repo;
  x: number;
  y: number;
}

interface ProjectsPanelProps {
  isVisible: boolean;
  isActive: boolean;
  onProjectClick?: (projectId: string) => void;
}

// ── GitHub fetch ──────────────────────────────────────────────────────────────
async function fetchStarredRepos(): Promise<Repo[]> {
  const token =
    (import.meta as any).env?.VITE_GITHUB_TOKEN ??
    localStorage.getItem("GITHUB_TOKEN") ??
    "";

  if (!token) throw new Error("No GITHUB_TOKEN found");

  let all: Repo[] = [];
  let page = 1;
  while (true) {
    const res = await fetch(
      `https://api.github.com/user/starred?per_page=100&page=${page}`,
      { headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" } }
    );
    if (!res.ok) throw new Error(`GitHub API error: ${res.status}`);
    const data: Repo[] = await res.json();
    if (data.length === 0) break;
    all = all.concat(data);
    if (data.length < 100) break;
    page++;
  }
  return all;
}

// ── Open helpers ──────────────────────────────────────────────────────────────
function openInCursor(repo: Repo) {
  const localPath = LOCAL_PATHS[repo.name];
  if (localPath) {
    window.location.href = `cursor://file${localPath}`;
  } else {
    window.open(repo.html_url, "_blank");
  }
  console.log("[Jarvis] open in Cursor:", repo.name, localPath ?? "(no local path)");
}

function openInKiro(repo: Repo) {
  const localPath = LOCAL_PATHS[repo.name];
  if (localPath) {
    // Kiro uses vscode:// scheme (it's a VS Code fork)
    window.location.href = `vscode://file${localPath}`;
  } else {
    window.open(repo.html_url, "_blank");
  }
  console.log("[Jarvis] open in Kiro:", repo.name, localPath ?? "(no local path)");
}

// ── Main component ────────────────────────────────────────────────────────────
export function ProjectsPanel({ isVisible, isActive, onProjectClick }: ProjectsPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const isScrolling = useRef(false);
  const scrollTimeout = useRef<NodeJS.Timeout | null>(null);

  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMenu, setActionMenu] = useState<ActionMenuState | null>(null);

  // Fetch starred repos when panel becomes visible
  useEffect(() => {
    if (!isVisible || repos.length > 0) return;
    setLoading(true);
    setError(null);
    fetchStarredRepos()
      .then((data) => {
        setRepos(data);
        setLoading(false);
      })
      .catch((e: Error) => {
        setError(e.message);
        setLoading(false);
      });
  }, [isVisible]);

  // Close action menu on outside click
  useEffect(() => {
    if (!actionMenu) return;
    const close = () => setActionMenu(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [actionMenu]);

  // Infinite scroll data: repeat repos 9× so scroll wraps
  const REPS = 9;
  const displayRepos: Repo[] =
    repos.length > 0
      ? repos
      : Array.from({ length: 5 }, (_, i) => ({
          id: i,
          name: loading ? "LOADING..." : "NO REPOS",
          full_name: "",
          html_url: "",
          description: null,
        }));
  const infiniteRepos = Array(REPS).fill(displayRepos).flat();

  // Infinite-scroll reset: jump back to middle section when near edges
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    setTimeout(() => {
      if (!el) return;
      const inner = el.querySelector(".projects-inner");
      if (!inner) return;
      const sectionH = (inner as HTMLElement).scrollHeight / REPS;
      el.scrollTop = sectionH * 4;
    }, 50);

    const onScroll = () => {
      const scrollH = el.scrollHeight;
      const sectionH = scrollH / REPS;
      const section = Math.floor(el.scrollTop / sectionH);
      const posInSection = el.scrollTop % sectionH;

      if (section < 2 || section > 6) {
        isScrolling.current = true;
        el.scrollTop = sectionH * 4 + posInSection;
        requestAnimationFrame(() => { isScrolling.current = false; });
        return;
      }

      if (isScrolling.current) return;
      if (scrollTimeout.current) clearTimeout(scrollTimeout.current);

      scrollTimeout.current = setTimeout(() => {
        if (isScrolling.current) return;
        const cards = el.querySelectorAll(".project-card");
        if (!cards.length) return;

        const cRect = el.getBoundingClientRect();
        const cCenter = cRect.top + cRect.height / 2;
        let closest: Element | null = null;
        let minDist = Infinity;

        cards.forEach((card) => {
          const r = card.getBoundingClientRect();
          const dist = Math.abs(r.top + r.height / 2 - cCenter);
          if (dist < minDist) { minDist = dist; closest = card; }
        });

        if (!closest) return;
        const r = (closest as Element).getBoundingClientRect();
        const offset = (r.top + r.height / 2) - cCenter;
        el.scrollTo({ top: el.scrollTop + offset, behavior: "smooth" });
      }, 150);
    };

    el.addEventListener("scroll", onScroll);
    return () => {
      el.removeEventListener("scroll", onScroll);
      if (scrollTimeout.current) clearTimeout(scrollTimeout.current);
    };
  }, [repos]);

  const handleCardClick = useCallback((repo: Repo, e: React.MouseEvent) => {
    if (!repo.html_url) return; // skip placeholder cards
    e.stopPropagation();
    setActionMenu({ repo, x: e.clientX, y: e.clientY });
    onProjectClick?.(repo.name);
    console.log("[Jarvis] project selected:", repo.name);
  }, [onProjectClick]);

  return (
    <>
      <motion.div
        className="absolute right-8 top-1/2 -translate-y-1/2 z-10"
        initial={{ x: 400, opacity: 0 }}
        animate={{ x: isVisible ? 0 : 400, opacity: isVisible ? 1 : 0 }}
        transition={{ type: "spring", stiffness: 250, damping: 28 }}
      >
        {/* Glass panel */}
        <div
          className="relative w-80 overflow-hidden rounded-3xl"
          style={{
            height: "420px",
            background: "linear-gradient(135deg, rgba(0,183,255,0.08) 0%, rgba(0,150,255,0.05) 50%, rgba(0,120,200,0.03) 100%)",
            backdropFilter: "blur(20px)",
            border: "1.5px solid rgba(0,183,255,0.25)",
            boxShadow: "0 8px 32px rgba(0,183,255,0.15), 0 4px 16px rgba(0,0,0,0.4), inset 0 2px 4px rgba(255,255,255,0.1), inset 0 -2px 4px rgba(0,0,0,0.2)",
          }}
        >
          {/* Shine */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{ background: "linear-gradient(135deg, rgba(255,255,255,0.12) 0%, transparent 50%, rgba(0,0,0,0.08) 100%)" }}
          />

          {/* Header */}
          <div className="relative px-6 py-5 border-b border-cyan-400/20">
            <motion.h2
              className="text-2xl font-light tracking-wide text-cyan-300 text-center"
              style={{ textShadow: "0 0 15px rgba(0,183,255,0.6), 0 0 30px rgba(0,183,255,0.3), 0 2px 4px rgba(0,0,0,0.5)" }}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              PROJECTS
            </motion.h2>
            {/* Status dot */}
            {!loading && !error && repos.length > 0 && (
              <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                <span className="text-[10px] text-cyan-400/60 font-light tracking-widest">{repos.length}</span>
              </div>
            )}
          </div>

          {/* Error state */}
          {error && (
            <div className="flex flex-col items-center justify-center h-[calc(100%-80px)] gap-2 px-6">
              <p className="text-cyan-500/60 text-xs text-center font-light tracking-wider">
                {error.includes("GITHUB_TOKEN")
                  ? "Set VITE_GITHUB_TOKEN in .env\nor localStorage.setItem('GITHUB_TOKEN', '...')"
                  : error}
              </p>
            </div>
          )}

          {/* Scrollable list */}
          {!error && (
            <div
              ref={scrollRef}
              className="relative overflow-y-auto overflow-x-hidden px-4 custom-scrollbar"
              style={{ height: "calc(100% - 80px)", perspective: "1200px", perspectiveOrigin: "center center" }}
            >
              <div className="projects-inner space-y-4 py-6">
                {infiniteRepos.map((repo, index) => (
                  <ProjectCard
                    key={`${repo.id}-${index}`}
                    repo={repo}
                    isPlaceholder={!repo.html_url}
                    isLoading={loading}
                    scrollContainer={scrollRef}
                    onClick={(e) => handleCardClick(repo, e)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Top / bottom fade masks */}
          <div
            className="absolute top-20 left-0 right-0 h-16 pointer-events-none z-10"
            style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0.6), transparent)" }}
          />
          <div
            className="absolute bottom-0 left-0 right-0 h-16 pointer-events-none z-10"
            style={{ background: "linear-gradient(to top, rgba(0,0,0,0.6), transparent)" }}
          />
        </div>

        <style>{`
          .custom-scrollbar { scrollbar-width: none; -ms-overflow-style: none; }
          .custom-scrollbar::-webkit-scrollbar { display: none; }
        `}</style>
      </motion.div>

      {/* Action menu */}
      <AnimatePresence>
        {actionMenu && (
          <motion.div
            key="action-menu"
            className="fixed z-50"
            style={{ left: actionMenu.x - 80, top: actionMenu.y - 10 }}
            initial={{ opacity: 0, scale: 0.85, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.85, y: 8 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="rounded-2xl overflow-hidden flex flex-col"
              style={{
                background: "linear-gradient(135deg, rgba(0,183,255,0.14) 0%, rgba(0,120,200,0.10) 100%)",
                backdropFilter: "blur(24px)",
                border: "1.5px solid rgba(0,183,255,0.3)",
                boxShadow: "0 8px 32px rgba(0,183,255,0.2), 0 4px 16px rgba(0,0,0,0.5)",
              }}
            >
              <div className="px-5 pt-4 pb-2 border-b border-cyan-400/20">
                <p
                  className="text-xs font-light tracking-widest text-cyan-300 text-center"
                  style={{ textShadow: "0 0 10px rgba(0,183,255,0.5)" }}
                >
                  {actionMenu.repo.name.toUpperCase()}
                </p>
              </div>
              <div className="flex gap-px">
                <ActionButton
                  label="CURSOR"
                  onClick={() => { openInCursor(actionMenu.repo); setActionMenu(null); }}
                />
                <ActionButton
                  label="KIRO"
                  onClick={() => { openInKiro(actionMenu.repo); setActionMenu(null); }}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ── Action button ─────────────────────────────────────────────────────────────
function ActionButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <motion.button
      className="flex-1 px-5 py-3 text-xs font-light tracking-widest text-cyan-300 relative overflow-hidden"
      onClick={onClick}
      whileHover={{ backgroundColor: "rgba(0,183,255,0.12)" }}
      whileTap={{ scale: 0.96 }}
      style={{ textShadow: "0 0 10px rgba(0,183,255,0.4)" }}
    >
      {label}
      <motion.div
        className="absolute inset-0 pointer-events-none"
        initial={{ opacity: 0 }}
        whileHover={{ opacity: 1 }}
        style={{ background: "linear-gradient(135deg, rgba(0,183,255,0.1), transparent)" }}
      />
    </motion.button>
  );
}

// ── Project card ──────────────────────────────────────────────────────────────
interface ProjectCardProps {
  repo: Repo;
  isPlaceholder: boolean;
  isLoading: boolean;
  scrollContainer: React.RefObject<HTMLDivElement>;
  onClick: (e: React.MouseEvent) => void;
}

function ProjectCard({ repo, isPlaceholder, isLoading, scrollContainer, onClick }: ProjectCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const scrollEl = scrollContainer.current;
    const cardEl = cardRef.current;
    if (!scrollEl || !cardEl) return;

    const update = () => {
      const cRect = scrollEl.getBoundingClientRect();
      const kRect = cardEl.getBoundingClientRect();
      const dist = (kRect.top + kRect.height / 2) - (cRect.top + cRect.height / 2);
      setScrollProgress(dist / (cRect.height / 2));
    };

    update();
    scrollEl.addEventListener("scroll", update);
    return () => scrollEl.removeEventListener("scroll", update);
  }, [scrollContainer]);

  const rotateX = scrollProgress * 15;
  const scale = 1 - Math.abs(scrollProgress) * 0.15;
  const opacity = Math.max(0.5, 1 - Math.abs(scrollProgress) * 0.5);
  const blur = Math.abs(scrollProgress) * 4;

  return (
    <motion.div
      ref={cardRef}
      className={`relative project-card ${isPlaceholder ? "pointer-events-none" : "cursor-pointer"}`}
      animate={{ opacity, rotateX, scale }}
      transition={{ opacity: { duration: 0.3 }, type: "spring", stiffness: 250, damping: 25 }}
      whileHover={isPlaceholder ? {} : { scale: scale * 1.05, rotateY: 5, z: 50 }}
      whileTap={isPlaceholder ? {} : { scale: scale * 0.98 }}
      onClick={isPlaceholder ? undefined : onClick}
      style={{ transformStyle: "preserve-3d", filter: `blur(${blur}px)` }}
    >
      {/* Card glow on hover */}
      {!isPlaceholder && (
        <motion.div
          className="absolute inset-0 rounded-2xl"
          style={{ background: "radial-gradient(circle at 50% 50%, rgba(0,183,255,0.3), transparent 70%)", filter: "blur(20px)" }}
          initial={{ opacity: 0 }}
          whileHover={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        />
      )}

      {/* Card body */}
      <div
        className="relative px-6 py-5 rounded-2xl overflow-hidden"
        style={{
          background: "linear-gradient(135deg, rgba(0,183,255,0.12) 0%, rgba(0,150,255,0.08) 50%, rgba(0,120,200,0.05) 100%)",
          backdropFilter: "blur(15px)",
          border: "1.5px solid rgba(0,183,255,0.2)",
          boxShadow: "0 4px 20px rgba(0,183,255,0.1), 0 2px 8px rgba(0,0,0,0.3), inset 0 1px 2px rgba(255,255,255,0.1), inset 0 -1px 2px rgba(0,0,0,0.2)",
          transformStyle: "preserve-3d",
        }}
      >
        <div className="absolute inset-0" style={{ background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 50%, rgba(0,0,0,0.05) 100%)" }} />
        {!isPlaceholder && (
          <motion.div
            className="absolute inset-0"
            style={{ background: "linear-gradient(135deg, rgba(0,183,255,0.15), rgba(0,150,255,0.1))" }}
            initial={{ opacity: 0 }}
            whileHover={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          />
        )}

        <motion.p
          className="relative text-2xl font-light tracking-wide text-cyan-300 text-center"
          style={{
            textShadow: "0 0 15px rgba(0,183,255,0.5), 0 0 30px rgba(0,183,255,0.3), 0 2px 4px rgba(0,0,0,0.5)",
            opacity: isLoading && isPlaceholder ? 0.4 : 1,
          }}
          whileHover={isPlaceholder ? {} : {
            textShadow: "0 0 20px rgba(0,183,255,0.8), 0 0 40px rgba(0,183,255,0.5), 0 2px 4px rgba(0,0,0,0.5)",
          }}
        >
          {repo.name}
        </motion.p>

        {/* Local path indicator */}
        {!isPlaceholder && LOCAL_PATHS[repo.name] && (
          <div className="relative mt-1 flex justify-center">
            <div className="w-1 h-1 rounded-full bg-cyan-400/50" />
          </div>
        )}

        <div className="absolute bottom-0 left-0 right-0 h-px" style={{ background: "linear-gradient(to right, transparent, rgba(0,183,255,0.5), transparent)" }} />
      </div>

      {/* Tap ripple */}
      {!isPlaceholder && (
        <motion.div
          className="absolute inset-0 rounded-2xl pointer-events-none"
          initial={{ scale: 0, opacity: 0.6 }}
          whileTap={{ scale: 2, opacity: 0 }}
          transition={{ duration: 0.5 }}
          style={{ background: "radial-gradient(circle, rgba(0,183,255,0.6), transparent 70%)" }}
        />
      )}
    </motion.div>
  );
}
