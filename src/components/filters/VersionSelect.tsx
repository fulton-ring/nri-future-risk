import { useId } from 'react';
import { Archive, FlaskConical } from 'lucide-react';
import { release, releases, selectionForRelease } from '../../data/releases';
import { track } from '../../analytics/track';
import FieldHelp from './FieldHelp';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

export default function VersionSelect() {
  const id = useId();
  return <div className="control-field version-field">
    <div className="field-label-row">
      <label htmlFor={id}>Data version</label>
      <FieldHelp label="Data version">
        <p><strong>FEMA archive (Dec 2024):</strong> FEMA’s original Future Risk Index, by county, before it was taken offline.</p>
        <p><strong>NRI v1.20:</strong> our recalculation on FEMA’s newer National Risk Index baseline, for counties or census tracts. It updates wildfire, drought and extreme heat.</p>
      </FieldHelp>
    </div>
    <Select value={release.id} onValueChange={(value) => {
      const url = new URL(window.location.href);
      url.searchParams.set('release', value);
      const selected = releases.find(item => item.id === value);
      if (selected && !selectionForRelease(url.searchParams.get('county') ?? '', release, selected)) url.searchParams.delete('county');
      track('data_version_changed', {from: release.id, to: value}, {beforeNavigation: true});
      window.location.assign(url);
    }}>
      <SelectTrigger id={id} className="atlas-select-trigger"><SelectValue /></SelectTrigger>
      <SelectContent className="atlas-select-content">
        {releases.map((item) => {
          const Icon = item.status === 'analysis' ? FlaskConical : Archive;
          const date = new Date(`${item.date}T00:00:00Z`).toLocaleDateString('en-US', {month: 'short', year: 'numeric', timeZone: 'UTC'});
          return <SelectItem key={item.id} value={item.id} className="atlas-select-item">
            <span className="select-option-label"><Icon size={17} strokeWidth={1.6} aria-hidden="true" /><span style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{item.geography ? item.title.replace(/\s*·\s*/g, ", ") : `${item.status === 'analysis' ? 'Analysis' : 'FEMA archive'} (${date})`} </span></span>
          </SelectItem>;
        })}
      </SelectContent>
    </Select>
  </div>;
}
