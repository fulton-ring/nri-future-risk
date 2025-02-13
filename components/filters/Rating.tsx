import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const Rating = () => {
  return (
    <Select>
      <SelectTrigger className="w-[180px]">
        <SelectValue placeholder="Select Rating" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="light">Projected Annual Loss</SelectItem>
        <SelectItem value="dark">Projected Risk Rating</SelectItem>
        <SelectItem value="system">Hazard Multiplier</SelectItem>
      </SelectContent>
    </Select>
  );
};

export default Rating;
