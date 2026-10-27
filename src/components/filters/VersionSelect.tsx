import { useId } from 'react';
import { Archive, FlaskConical } from 'lucide-react';
import { release, releases } from '../../data/releases';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

export default function VersionSelect() {
  const id = useId();
  return <div className="control-field version-field">
    <label htmlFor={id}>Data version</label>
    <Select value={release.id} onValueChange={(value) => {
      const url = new URL(window.location.href);
      url.searchParams.set('release', value);
      window.location.assign(url);
    }}>
      <SelectTrigger id={id} className="atlas-select-trigger"><SelectValue /></SelectTrigger>
      <SelectContent className="atlas-select-content">
        {releases.map((item) => {
          const Icon = item.status === 'analysis' ? FlaskConical : Archive;
          const date = new Date(`${item.date}T00:00:00Z`).toLocaleDateString('en-US', {month: 'short', year: 'numeric', timeZone: 'UTC'});
          return <SelectItem key={item.id} value={item.id} className="atlas-select-item">
            <span className="select-option-label"><Icon size={17} strokeWidth={1.6} aria-hidden="true" /><span>{item.status === 'analysis' ? 'Analysis' : 'FEMA archive'} · {date}</span></span>
          </SelectItem>;
        })}
      </SelectContent>
    </Select>
  </div>;
}
