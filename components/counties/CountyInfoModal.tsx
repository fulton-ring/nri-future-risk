import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { CountyProperties } from "@/schema/county";

interface CountyInfoModalProps {
  selectedCounty: CountyProperties | undefined;
  onClose: () => void;
}

const CountyInfoModal = ({ selectedCounty, onClose }: CountyInfoModalProps) => {
  if (!selectedCounty) {
    return <></>;
  }

  return (
    <Dialog
      open={true}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{selectedCounty.coty_name[0]}</DialogTitle>
          <DialogDescription>
            {selectedCounty.coty_name_long[0]}
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  );
};

export default CountyInfoModal;
