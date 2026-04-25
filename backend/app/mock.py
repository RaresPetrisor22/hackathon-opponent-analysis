from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.dossier import (
    ArchetypeRecord,
    DossierResponse,
    FormSection,
    GameplanNarrative,
    GameStateRecord,
    GameStateSection,
    IdentitySection,
    MatchFormEntry,
    MatchupSection,
    PlayerCard,
    PlayerCardsSection,
    RefereeSection,
    TacticalIdentityStats,
)


def build_mock_dossier(team_id: int, team_name: str = "CFR Cluj") -> DossierResponse:
    form = FormSection(
        last_5=[
            MatchFormEntry(date="2025-04-12", opponent="FCSB", home_away="H", goals_for=2, goals_against=1, result="W"),
            MatchFormEntry(date="2025-04-05", opponent="Rapid", home_away="A", goals_for=0, goals_against=0, result="D"),
            MatchFormEntry(date="2025-03-29", opponent="Petrolul", home_away="H", goals_for=3, goals_against=1, result="W"),
            MatchFormEntry(date="2025-03-22", opponent="Dinamo", home_away="A", goals_for=1, goals_against=2, result="L"),
            MatchFormEntry(date="2025-03-15", opponent="Sepsi", home_away="H", goals_for=2, goals_against=0, result="W"),
        ],
        last_10=[
            MatchFormEntry(date="2025-04-12", opponent="FCSB", home_away="H", goals_for=2, goals_against=1, result="W"),
            MatchFormEntry(date="2025-04-05", opponent="Rapid", home_away="A", goals_for=0, goals_against=0, result="D"),
            MatchFormEntry(date="2025-03-29", opponent="Petrolul", home_away="H", goals_for=3, goals_against=1, result="W"),
            MatchFormEntry(date="2025-03-22", opponent="Dinamo", home_away="A", goals_for=1, goals_against=2, result="L"),
            MatchFormEntry(date="2025-03-15", opponent="Sepsi", home_away="H", goals_for=2, goals_against=0, result="W"),
            MatchFormEntry(date="2025-03-08", opponent="U Craiova", home_away="A", goals_for=1, goals_against=1, result="D"),
            MatchFormEntry(date="2025-03-01", opponent="Hermannstadt", home_away="H", goals_for=2, goals_against=0, result="W"),
            MatchFormEntry(date="2025-02-22", opponent="Otelul", home_away="A", goals_for=0, goals_against=1, result="L"),
            MatchFormEntry(date="2025-02-15", opponent="Poli Iasi", home_away="H", goals_for=3, goals_against=0, result="W"),
            MatchFormEntry(date="2025-02-08", opponent="Farul", home_away="A", goals_for=1, goals_against=2, result="L"),
        ],
        wins_last5=3,
        draws_last5=1,
        losses_last5=1,
        goals_scored_avg=1.8,
        goals_conceded_avg=0.8,
        form_string="WDWLW",
    )

    # Opponent (CFR Cluj) tactical profile — dominant possession side.
    identity = IdentitySection(
        stats=TacticalIdentityStats(
            avg_possession=57.4,
            avg_shots=14.1,
            avg_shots_on_target=5.3,
            avg_pass_accuracy=84.6,
            avg_fouls=11.2,
            avg_yellow_cards=1.8,
            avg_corners=6.1,
            preferred_formation="4-3-3",
        ),
        pressing_intensity="medium",
        play_style="possession-based build-up",
        notes=(
            "Possession-based build-up side averaging 57% possession, 14.1 shots "
            "(5.3 on target) and 6.1 corners per match. Pressing intensity reads as "
            "medium (11.2 fouls/match). Default shape: 4-3-3."
        ),
    )

    # FCU (U Cluj) tactical profile — compact counter-attacking side.
    fcu_profile = TacticalIdentityStats(
        avg_possession=46.8,
        avg_shots=10.9,
        avg_shots_on_target=3.6,
        avg_pass_accuracy=74.3,
        avg_fouls=13.8,
        avg_yellow_cards=2.3,
        avg_corners=4.2,
        preferred_formation="4-2-3-1",
    )

    # Archetypes match the real pipeline labels from analysis/matchups.py.
    # Records represent CFR Cluj's W/D/L when facing teams of each archetype.
    # fcu_archetype_id=2 → "Compact Counter" (FCU's classification).
    matchups = MatchupSection(
        archetypes=[
            ArchetypeRecord(
                archetype_id=1,
                archetype_name="Dominant Possession Elite",
                archetype_description=(
                    "High possession, high pass accuracy, positive goal differential. "
                    "Imposes its rhythm on opponents and out-passes them in build-up. "
                    "Big-Four profile in the 2024-25 SuperLiga."
                ),
                matches_played=6,
                wins=2,
                draws=2,
                losses=2,
                goals_for=1.17,
                goals_against=1.33,
                xg_diff=-0.28,
            ),
            ArchetypeRecord(
                archetype_id=2,
                archetype_name="Compact Counter",
                archetype_description=(
                    "Mid-range possession, decent pass accuracy, neutral-to-positive goal "
                    "differential. Pragmatic teams that absorb pressure and break "
                    "efficiently — middle-of-the-table operators."
                ),
                matches_played=8,
                wins=5,
                draws=2,
                losses=1,
                goals_for=1.88,
                goals_against=0.75,
                xg_diff=0.54,
            ),
            ArchetypeRecord(
                archetype_id=3,
                archetype_name="Long-Range Specialists",
                archetype_description=(
                    "Elevated long-shot ratio with low shot quality. Outshoots opponents "
                    "from distance but converts poorly — speculative attacking pattern."
                ),
                matches_played=7,
                wins=5,
                draws=1,
                losses=1,
                goals_for=2.14,
                goals_against=0.86,
                xg_diff=0.71,
            ),
            ArchetypeRecord(
                archetype_id=4,
                archetype_name="Direct & Struggling",
                archetype_description=(
                    "Low possession, low pass accuracy, negative goal differential. "
                    "Bypasses midfield with direct play but lacks the quality to "
                    "convert chances. Lower-table profile."
                ),
                matches_played=9,
                wins=8,
                draws=1,
                losses=0,
                goals_for=2.78,
                goals_against=0.56,
                xg_diff=1.12,
            ),
        ],
        fcu_archetype_id=2,
        fcu_archetype_name="Compact Counter",
        prediction_summary=(
            "Against teams that play like U Cluj ('Compact Counter'), "
            f"{team_name} performs above their usual level — 62% win rate "
            "versus 53% season-wide. Their organised high line and ball-winning "
            "midfield are well-suited to neutralising compact defensive blocks.\n\n"
            "Their defence tightens markedly against this style — 0.75 goals conceded "
            "per game versus 0.87 season average. Patience will be required in the "
            "final third; chances must be converted at a higher rate than usual.\n\n"
            "U Cluj's natural style is not the opponent's statistical weak spot. "
            "Their lowest win rate (33%) comes against 'Dominant Possession Elite' "
            "teams — if a tactical shift is needed, borrowing build-up elements "
            "from that archetype would maximise the disruption."
        ),
        best_archetype_vs_opponent="Dominant Possession Elite",
        fcu_tactical_profile=fcu_profile,
    )

    players = PlayerCardsSection(
        key_threats=[
            PlayerCard(
                player_id=101,
                name="Billel Omrani",
                position="Attacker",
                jersey_number=9,
                photo_url=None,
                key_stats={"goals": 11.0, "assists": 4.0, "shots_per_game": 3.2, "dribbles_won": 1.8},
                threat_level="high",
                notes="Clinical finisher in and around the box. Dangerous on the turn. Provide tight physical cover at centre-back.",
            ),
            PlayerCard(
                player_id=102,
                name="Ciprian Deac",
                position="Midfielder",
                jersey_number=10,
                photo_url=None,
                key_stats={"goals": 5.0, "assists": 9.0, "key_passes": 2.7, "pass_accuracy": 87.0},
                threat_level="high",
                notes="Creative hub and set-piece delivery. Deny him space between the lines — press his reception early.",
            ),
            PlayerCard(
                player_id=103,
                name="Mihai Bordeianu",
                position="Midfielder",
                jersey_number=8,
                photo_url=None,
                key_stats={"goals": 3.0, "assists": 2.0, "tackles": 3.1, "interceptions": 2.4},
                threat_level="medium",
                notes="Box-to-box engine with high work rate. Watch for late runs into the box from deep positions.",
            ),
        ],
        defensive_vulnerabilities=[
            PlayerCard(
                player_id=201,
                name="Andrei Burca",
                position="Defender",
                jersey_number=5,
                photo_url=None,
                key_stats={"fouls": 2.1, "yellow_cards": 0.3, "duels_won_pct": 58.0, "aerial_won_pct": 61.0},
                threat_level="medium",
                notes="Steps out aggressively to press — space opens in behind on quick transitions. Target with runs in behind.",
            ),
            PlayerCard(
                player_id=202,
                name="Camora",
                position="Defender",
                jersey_number=3,
                photo_url=None,
                key_stats={"fouls": 1.8, "yellow_cards": 0.4, "duels_won_pct": 52.0, "crosses_blocked": 0.9},
                threat_level="low",
                notes="Left back who pushes high and leaves the channel exposed. Primary counter-attack route on turnovers.",
            ),
        ],
    )

    game_state = GameStateSection(
        records=[
            GameStateRecord(
                state="winning",
                matches=18,
                avg_goals_for=0.61,
                avg_goals_against=0.22,
                defensive_change="Drops into a deep 4-4-2 block, reduces pressing intensity significantly.",
                offensive_change="Prioritises ball retention over chance creation — game management mode.",
            ),
            GameStateRecord(
                state="drawing",
                matches=9,
                avg_goals_for=1.22,
                avg_goals_against=0.89,
                defensive_change="Maintains shape and waits for opponent mistakes.",
                offensive_change="Increases tempo and introduces a more direct second striker.",
            ),
            GameStateRecord(
                state="losing",
                matches=7,
                avg_goals_for=1.57,
                avg_goals_against=1.71,
                defensive_change="Abandons compact shape — becomes stretched and vulnerable on the counter.",
                offensive_change="Goes direct: long balls to the striker, crosses from wide areas.",
            ),
        ],
        tendency_when_losing="Shifts to long-ball direct play; defensive shape breaks down — exploitable on the counter.",
        tendency_when_winning="Extreme low-block; virtually no offensive output — pure game management.",
    )

    referee = RefereeSection(
        referee_name="Istvan Kovacs",
        total_matches=24,
        avg_yellow_cards=3.8,
        avg_red_cards=0.21,
        avg_fouls_called=22.4,
        home_advantage_factor=0.54,
        notes="Lenient on physical duels in the opening 30 minutes. Card rate rises sharply after the 60th minute. Consistent with offside calls; rarely plays advantage.",
    )

    gameplan = GameplanNarrative(
        headline=f"Hold the block, release early — exploit the channel behind Camora.",
        body=(
            f"{team_name} are well-organised in possession but structurally exposed when play is "
            "turned over quickly. Their left channel is the primary vulnerability — Camora pushes "
            "high and leaves space in behind that fast wide forwards can target with timed runs.\n\n"
            "U Cluj's 'Compact Counter' archetype concedes a 62% opponent win rate against "
            f"{team_name} — this is a challenging matchup in our natural style. Sit compact in a "
            "4-2-3-1 mid-block, absorb their possession-based build-up, and release quickly "
            "through the channels on turnovers. Limit the half-spaces to deny Deac time on the ball.\n\n"
            f"{team_name} concede only 0.22 goals per game when winning — do not allow them to take "
            "the lead. If the score is level past the 70th minute, they will increase tempo and "
            "expose their own defensive shape. Referee Kovacs books heavily after 60 minutes — "
            "discipline in the second half is non-negotiable."
        ),
        key_actions=[
            "Hold a compact 4-2-3-1 mid-block — do not press high until the ball reaches their centre-backs.",
            "Target Camora's channel with timed runs from the right winger on every turnover.",
            "Assign a shadow runner to Deac at all times — deny him the half-space reception.",
            "Win the second ball in midfield — Bordeianu's late runs must be tracked by the double pivot.",
            "If leading after 70 minutes: drop to a deep 4-5-1 and manage the game — do not invite pressure.",
        ],
    )

    return DossierResponse(
        opponent_id=team_id,
        opponent_name=team_name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        form=form,
        identity=identity,
        matchups=matchups,
        players=players,
        game_state=game_state,
        referee=referee,
        gameplan=gameplan,
    )
