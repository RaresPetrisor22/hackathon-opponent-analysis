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
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-[10px] font-mono text-accent uppercase tracking-widest">
            Pre-Match Dossier · FC Universitatea Cluj
          </p>
          <div className="flex items-center gap-3">
            {dossier.opponent_logo_url && (
              <Image
                src={dossier.opponent_logo_url}
                alt={dossier.opponent_name}
                width={48}
                height={48}
                className="object-contain"
              />
            )}
            <h1 className="text-3xl font-bold text-white">{dossier.opponent_name}</h1>
          </div>
          <p className="text-muted-fg text-xs font-mono">
            Generated {new Date(dossier.generated_at).toLocaleString()}
          </p>
        </div>
        <PrintButton />
      </div>

      {/* Hero section */}
      <section className="w-full">
        <MatchupIntelligence data={dossier.matchups} opponentIdentity={dossier.identity.stats} opponentName={dossier.opponent_name} />
      </section>

      {/* Supporting analysis divider */}
      <div className="flex items-center gap-4 pt-2">
        <div className="h-px flex-1 bg-surface-2" />
        <span className="text-[10px] font-mono text-muted-fg uppercase tracking-widest">
          Supporting Analysis
        </span>
        <div className="h-px flex-1 bg-surface-2" />
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
