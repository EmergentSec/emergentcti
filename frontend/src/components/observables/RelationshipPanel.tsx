import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { ObservableBadge } from '@/components/observables/ObservableBadge';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { AddRelationshipDialog } from '@/components/observables/AddRelationshipDialog';
import { useRelationships, useDeleteRelationship } from '@/hooks/useRelationships';
import { useAuth } from '@/hooks/useAuth';
import { isAnalyst, canDelete } from '@/lib/permissions';
import { useToast } from '@/contexts/ToastContext';
import { truncate } from '@/lib/utils';
import type { RelationshipResponse } from '@/types/relationship';

interface RelationshipPanelProps {
  observableId: string;
}

export function RelationshipPanel({ observableId }: RelationshipPanelProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { addToast } = useToast();
  const { data: relationships = [], isLoading } = useRelationships(observableId);
  const deleteMutation = useDeleteRelationship();
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleDelete = (relationshipId: string) => {
    deleteMutation.mutate(relationshipId, {
      onSuccess: () => {
        addToast('Relationship deleted', 'success');
      },
      onError: () => {
        addToast('Failed to delete relationship', 'error');
      },
    });
  };

  const getDirection = (rel: RelationshipResponse): 'outgoing' | 'incoming' => {
    return rel.source_id === observableId ? 'outgoing' : 'incoming';
  };

  const getRelatedObservable = (rel: RelationshipResponse) => {
    const direction = getDirection(rel);
    return direction === 'outgoing' ? rel.target : rel.source;
  };

  const getRelatedObservableId = (rel: RelationshipResponse) => {
    const direction = getDirection(rel);
    return direction === 'outgoing' ? rel.target_id : rel.source_id;
  };

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">
              Relationships
              {relationships.length > 0 && (
                <Badge variant="secondary" className="ml-2 tabular-nums">
                  {relationships.length}
                </Badge>
              )}
            </CardTitle>
            {isAnalyst(user) && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDialogOpen(true)}
              >
                Add Relationship
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner size="sm" />
            </div>
          ) : relationships.length === 0 ? (
            <p className="text-sm text-muted-foreground italic py-4 text-center">
              No relationships found. Link this observable to related indicators.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12"></TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Observable</TableHead>
                  <TableHead className="w-24 text-right">Confidence</TableHead>
                  {canDelete(user) && (
                    <TableHead className="w-12"></TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {relationships.map((rel) => {
                  const direction = getDirection(rel);
                  const related = getRelatedObservable(rel);
                  const relatedId = getRelatedObservableId(rel);

                  return (
                    <TableRow key={rel.id}>
                      {/* Direction Arrow */}
                      <TableCell className="text-center">
                        <span
                          className="text-muted-foreground text-lg"
                          title={direction === 'outgoing' ? 'Outgoing' : 'Incoming'}
                        >
                          {direction === 'outgoing' ? (
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              className="inline-block text-blue-400"
                            >
                              <line x1="5" y1="12" x2="19" y2="12" />
                              <polyline points="12 5 19 12 12 19" />
                            </svg>
                          ) : (
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              className="inline-block text-amber-400"
                            >
                              <line x1="19" y1="12" x2="5" y2="12" />
                              <polyline points="12 19 5 12 12 5" />
                            </svg>
                          )}
                        </span>
                      </TableCell>

                      {/* Relationship Type */}
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-xs">
                          {rel.relationship_type}
                        </Badge>
                      </TableCell>

                      {/* Related Observable */}
                      <TableCell>
                        {related ? (
                          <button
                            className="flex items-center gap-2 hover:underline text-left group"
                            onClick={() => navigate(`/observables/${relatedId}`)}
                          >
                            <ObservableBadge type={related.type as import('@/types/observable').ObservableType} />
                            <span className="text-sm font-mono text-muted-foreground group-hover:text-foreground transition-colors">
                              {truncate(related.value, 40)}
                            </span>
                          </button>
                        ) : (
                          <span className="text-sm text-muted-foreground italic">
                            Unknown
                          </span>
                        )}
                      </TableCell>

                      {/* Confidence */}
                      <TableCell className="text-right">
                        <span
                          className={`text-sm font-medium tabular-nums ${
                            rel.confidence >= 75
                              ? 'text-green-400'
                              : rel.confidence >= 50
                                ? 'text-amber-400'
                                : 'text-red-400'
                          }`}
                        >
                          {rel.confidence}
                        </span>
                      </TableCell>

                      {/* Delete Button */}
                      {canDelete(user) && (
                        <TableCell>
                          <button
                            onClick={() => handleDelete(rel.id)}
                            className="text-muted-foreground hover:text-destructive transition-colors p-1"
                            aria-label="Delete relationship"
                            disabled={deleteMutation.isPending}
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                              <line x1="10" y1="11" x2="10" y2="17" />
                              <line x1="14" y1="11" x2="14" y2="17" />
                            </svg>
                          </button>
                        </TableCell>
                      )}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <AddRelationshipDialog
        observableId={observableId}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </>
  );
}
