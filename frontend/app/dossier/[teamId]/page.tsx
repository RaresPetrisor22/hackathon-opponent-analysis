import Image from "next/image";
import { fetchDossier } from "@/lib/api";
import { FormPanel } from "@/components/dossier/FormPanel";
import { IdentityCard } from "@/components/dossier/IdentityCard";
import { MatchupIntelligence } from "@/components/dossier/MatchupIntelligence";
import { PlayerCards } from "@/components/dossier/PlayerCards";
import { GameStatePanel } from "@/components/dossier/GameStatePanel";
import { RefereeCard } from "@/components/dossier/RefereeCard";
import { GameplanNarrative } from "@/components/dossier/GameplanNarrative";
import { PrintButton } from "@/components/dossier/PrintButton";
import { ChatWidgetWrapper } from "@/components/dossier/ChatWidgetWrapper";

interface Props {
  params: { teamId: string };
}

export default async function DossierPage({ params }: Props) {
  const teamId = parseInt(params.teamId, 10);
  const dossier = await fetchDossier(teamId);

  return (
    <div id="dossier-content" className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Page header — editorial masthead */}
      <div className="flex items-end justify-between gap-6 border-b border-surface-2 pb-6">
        <div className="space-y-3 min-w-0">
          <div className="flex items-center gap-3">
            <span className="h-px w-10 bg-accent" />
            <p className="text-[10px] font-mono text-accent uppercase tracking-[0.3em]">
              Pre-Match Dossier
            </p>
          </div>
          <div className="flex items-end gap-5">
            {dossier.opponent_logo_url && (
              <Image
                src={dossier.opponent_logo_url}
                alt={dossier.opponent_name}
                width={72}
                height={72}
                className="object-contain shrink-0"
              />
            )}
            <h1 className="font-bold text-white uppercase tracking-tight leading-[0.9] text-5xl sm:text-6xl break-words">
              {dossier.opponent_name}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] font-mono text-muted-fg uppercase tracking-[0.18em]">
            <span className="text-white/70">FC Universitatea Cluj</span>
            <span className="text-surface-2">/</span>
            <span>2024–25 Season</span>
            <span className="text-surface-2">/</span>
            <span>Generated {new Date(dossier.generated_at).toLocaleDateString()}</span>
          </div>
        </div>
        <PrintButton />
      </div>

      {/* Hero section */}
      <section className="w-full">
        <MatchupIntelligence data={dossier.matchups} opponentIdentity={dossier.identity.stats} opponentName={dossier.opponent_name} />
      </section>

      {/* Supporting analysis divider — editorial rule */}
      <div className="flex items-center gap-4 pt-2">
        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-surface-2 to-surface-2" />
        <div className="flex items-center gap-2 px-2 py-1 border border-surface-2 rounded-sm bg-surface/40">
          <span className="size-1 rounded-full bg-accent" />
          <span className="text-[10px] font-mono text-muted-fg uppercase tracking-[0.3em]">
            Supporting Analysis
          </span>
        </div>
        <div className="h-px flex-1 bg-gradient-to-l from-transparent via-surface-2 to-surface-2" />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 print:grid-cols-1">
        <FormPanel data={dossier.form} />
        <IdentityCard data={dossier.identity} />
        <RefereeCard data={dossier.referee} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 print:grid-cols-1">
        <PlayerCards data={dossier.players} />
        <GameStatePanel data={dossier.game_state} />
      </div>

      <section className="w-full">
        <GameplanNarrative data={dossier.gameplan} />
      </section>

      {/* Floating chat assistant */}
      <ChatWidgetWrapper dossier={dossier as unknown as Record<string, unknown>} />
    </div>
  );
}
