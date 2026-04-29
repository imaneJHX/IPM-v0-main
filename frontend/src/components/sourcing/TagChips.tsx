/**
 * TagChips — Displays AI-generated tags with colour coding and dismiss functionality.
 */

"use client";

import type { Tags } from "@/lib/types";

interface TagChipsProps {
    tags: Tags;
    dismissedTags: Set<string>;
    onDismiss: (tagKey: string) => void;
}

const TAG_COLORS: Record<string, string> = {
    objectif: "amber",
    domaine: "blue",
    impact: "green",
    origine: "purple",
};

export function TagChips({ tags, dismissedTags, onDismiss }: TagChipsProps) {
    const chips: Array<{ key: string; label: string; color: string }> = [];

    if (tags.objectif) {
        chips.push({ key: `obj-${tags.objectif}`, label: tags.objectif, color: TAG_COLORS.objectif });
    }

    tags.domaine.forEach((d) => {
        chips.push({ key: `dom-${d}`, label: d, color: TAG_COLORS.domaine });
    });

    tags.impact.forEach((imp) => {
        chips.push({ key: `imp-${imp}`, label: imp, color: TAG_COLORS.impact });
    });

    if (tags.origine) {
        chips.push({ key: `ori-${tags.origine}`, label: tags.origine, color: TAG_COLORS.origine });
    }

    if (chips.length === 0) return null;

    return (
        <div className="tags-row">
            {chips.map((chip) => (
                <span
                    key={chip.key}
                    className={`tag-chip ${chip.color}${dismissedTags.has(chip.key) ? " dismissed" : ""}`}
                    onClick={() => onDismiss(chip.key)}
                >
                    {chip.label}
                    {!dismissedTags.has(chip.key) && (
                        <button className="tag-chip-x" aria-label="Dismiss">×</button>
                    )}
                </span>
            ))}
        </div>
    );
}
