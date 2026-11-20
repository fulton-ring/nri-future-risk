import type { ReactNode } from "react";
import { CircleHelp } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";

/** A question-mark button beside a field label that explains the field. Opens on tap as well as click. */
export default function FieldHelp({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className="field-help" aria-label={`About ${label}`}>
          <CircleHelp size={14} aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent side="top" align="start" className="field-help-content">
        {children}
      </PopoverContent>
    </Popover>
  );
}
