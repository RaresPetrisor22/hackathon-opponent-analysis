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
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{dossier.opponent_name}</h1>
          <p className="text-muted-fg text-xs font-mono mt-1">
            Generated {new Date(dossier.generated_at).toLocaleString()}
          </p>
        </div>
        <PrintButton />
      </div>

      {/* Hero row */}
      <section className="w-full">
        <MatchupIntelligence data={dossier.matchups} />
      </section>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <FormPanel data={dossier.form} />
        <IdentityCard data={dossier.identity} />
        <RefereeCard data={dossier.referee} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
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
