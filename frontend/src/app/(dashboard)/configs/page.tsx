'use client';

import { useCallback } from 'react';
import { PageTransition } from '@/components/layout/page-transition';
import { ConfigList } from '@/components/dashboard/config-list';
import { ConfigForm } from '@/components/dashboard/config-form';
import { DeleteConfirmation, UndoToast } from '@/components/dashboard/delete-confirmation';
import { useConfigs } from '@/hooks/use-configs';
import type { CreateConfigRequest, UpdateConfigRequest } from '@/types/config';

export default function ConfigsPage() {
  const {
    configurations,
    activeConfigId,
    maxAllowed,
    isLoading,
    isCreating,
    isUpdating,
    isDeleting,
    isFormOpen,
    editingConfig,
    deletingConfigId,
    createConfig,
    updateConfig,
    deleteConfig,
    setActiveConfig,
    openCreateForm,
    openEditForm,
    closeForm,
    startDelete,
    cancelDelete,
  } = useConfigs();

  // Handle form submission
  const handleFormSubmit = useCallback(
    (data: CreateConfigRequest | UpdateConfigRequest) => {
      if (editingConfig) {
        updateConfig(editingConfig.configId, data as UpdateConfigRequest);
      } else {
        createConfig(data as CreateConfigRequest);
      }
    },
    [editingConfig, createConfig, updateConfig]
  );

  // Handle delete confirmation
  const handleDeleteConfirm = useCallback(() => {
    if (deletingConfigId) {
      deleteConfig(deletingConfigId);
      cancelDelete();
    }
  }, [deletingConfigId, deleteConfig, cancelDelete]);

  // Find config being deleted for the confirmation dialog
  const deletingConfig = deletingConfigId
    ? configurations.find((c) => c.configId === deletingConfigId)
    : null;

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header - only show on mobile since desktop has sidebar */}
        <div className="md:hidden">
          <h1 className="text-2xl font-bold text-foreground">Configurations</h1>
          <p className="text-muted-foreground mt-1">
            Manage your sentiment tracking configurations
          </p>
        </div>

        {/* Configuration list */}
        <ConfigList
          configurations={configurations}
          activeConfigId={activeConfigId}
          maxAllowed={maxAllowed}
          isLoading={isLoading}
          onSelect={setActiveConfig}
          onEdit={openEditForm}
          onDelete={startDelete}
          onCreate={openCreateForm}
        />

        {/* Create/Edit form modal */}
        <ConfigForm
          isOpen={isFormOpen}
          editingConfig={editingConfig}
          onClose={closeForm}
          onSubmit={handleFormSubmit}
          isLoading={isCreating || isUpdating}
        />

        {/* Delete confirmation dialog */}
        <DeleteConfirmation
          isOpen={!!deletingConfigId}
          itemName={deletingConfig?.name || ''}
          onConfirm={handleDeleteConfirm}
          onCancel={cancelDelete}
          isDeleting={isDeleting}
        />
      </div>
    </PageTransition>
  );
}
