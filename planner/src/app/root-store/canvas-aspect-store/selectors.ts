import { MemoizedSelector, createFeatureSelector, createSelector } from '@ngrx/store';

import { CanvasAspect } from '../../models';
import { featureAdapter, State } from './state';

export const selectCanvasAspectState: MemoizedSelector<object, State> = createFeatureSelector<
  State
>('canvasAspect');

export const selectAllCanvasAspectItems: (
  state: object
) => CanvasAspect[] = featureAdapter.getSelectors(selectCanvasAspectState).selectAll;

export const selectCanvasAspectById = (id: string) =>
  createSelector(
    selectAllCanvasAspectItems,
    (allCanvasAspects: CanvasAspect[]) => {
      if (allCanvasAspects) {
        return allCanvasAspects.find(p => p.id === id);
      } else {
        return null;
      }
    }
  );

export const selectAddedCanvasAspects = createSelector(
  selectCanvasAspectState,
  state => state.addedIds.map(id => state.entities[id])
);
