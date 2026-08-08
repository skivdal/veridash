1: # Changes Needed for Metadata Widget
2: 
3: ## Change 1: Add Import (After line 8)
4: Add this line after `import shareIconPaths from '../imports/Vector-1/svg-d2217cmjm3';`:
5: ```
6: import { MetadataExpandedView } from './components/MetadataExpandedView';
7: ```
8: 
9: ## Change 2: Revert MetadataWidget to Toggle Version
10: The MetadataWidget function (starting around line 614) needs to:
11: - Add `const [viewMode, setViewMode] = useState<'raw' | 'analyze'>('raw');` after the function declaration
12: - Replace the side-by-side grid layout with toggle buttons and conditional rendering
13: 
14: ## Change 3: Update Expanded Widget View (Line 2761)
15: Change `<MetadataWidget />` to `<MetadataExpandedView />`
16: 