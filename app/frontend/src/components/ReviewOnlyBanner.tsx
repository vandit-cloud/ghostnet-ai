import { formatConfidence } from "@/utils/format";

import type { Detection } from "@/types";

/**
 * The review_only callout.
 *
 * The console shows a raw score and a calibrated confidence side by side, and
 * until now nothing on the page said which one to trust or why there are two.
 * That gap matters more here than anywhere else in the product: two deliberately
 * different score scales is the contract's central rule, and a detection screen
 * that presents both without framing invites exactly the misreading the rule
 * exists to prevent — treating a raw softmax output as a probability.
 *
 * It is also where the review gate is stated. Nothing in this system is a
 * confirmed find; every record is a candidate carrying an honest position
 * error, and it stays that way until a human signs it off.
 *
 * The mockup leads the review screen with this, as a sky band against an
 * imperial edge, and that is what it is.
 */
export function ReviewOnlyBanner({ detection }: { detection: Detection }) {
  const calibrated = formatConfidence(detection.calibrated_confidence);
  const error = detection.position_error_m;

  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-2 border-l-[5px] border-l-imperial bg-skytint px-[18px] py-3.5"
      role="note"
    >
      <p className="shrink-0 font-display text-[24px] font-extrabold uppercase leading-none tracking-[0.03em] text-imperial">
        Review only
      </p>
      <p className="flex-1 text-[13.5px] font-light leading-[1.6] text-imperial/80">
        This is a candidate finding, not a confirmed location of gear, and not a navigational
        product. The score beside it is{" "}
        <b className="font-mono text-[12.5px] font-medium">calibrated_confidence</b>
        {calibrated ? (
          <>
            {" "}
            (<b className="font-mono text-[12.5px] font-medium">{calibrated}</b>)
          </>
        ) : null}{" "}
        — never the raw model output, which is shown only for audit.
        {error !== null ? (
          <>
            {" "}
            Position is accurate to about{" "}
            <b className="font-mono text-[12.5px] font-medium">± {error} m</b>.
          </>
        ) : null}{" "}
        It stays flagged until a human signs it off.
      </p>
    </div>
  );
}
