const compact = new Intl.NumberFormat('en-US', {notation:'compact',maximumSignificantDigits:3});
const dollars = new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',notation:'compact',maximumSignificantDigits:3});
const exact = new Intl.NumberFormat('en-US', {maximumFractionDigits:20});
const valid = (value:number|null):value is number => value !== null && Number.isFinite(value);
export const formatNumber = (value:number|null) => valid(value) ? compact.format(value) : 'Unavailable';
export const formatDollars = (value:number|null) => valid(value) ? dollars.format(value) : 'Unavailable';
export const formatExactNumber = (value:number|null) => valid(value) ? exact.format(value) : 'Unavailable';
