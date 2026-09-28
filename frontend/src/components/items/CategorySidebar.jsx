import CategoryNode from "./CategoryNode";

/**
 * Left sidebar showing the category tree with selection, expand/collapse,
 * and CRUD actions. Includes the "All Items" button and "+ Add" trigger.
 */
export default function CategorySidebar({
  categoryTree,
  expandedCategories,
  selectedCategory,
  onToggleExpand,
  onSelectCategory,
  onEditCategory,
  onShowCategoryModal,
  onAddCategory,
  onDeleteCategory,
}) {
  return (
    <div className="w-full md:w-64 flex-shrink-0">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-white">Categories</h2>
          <button
            onClick={onAddCategory}
            className="text-blue-400 hover:text-blue-300 text-sm"
          >
            + Add
          </button>
        </div>

        <button
          onClick={() => onSelectCategory(null)}
          className={`w-full text-left px-3 py-2 rounded-lg text-sm mb-2 transition-colors ${
            selectedCategory === null
              ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
              : "text-gray-400 hover:bg-gray-800 hover:text-white"
          }`}
        >
          All Items
        </button>

        <div className="space-y-1">
          {categoryTree.map((node) => (
            <CategoryNode
              key={node.id}
              node={node}
              expandedCategories={expandedCategories}
              selectedCategory={selectedCategory}
              toggleExpand={onToggleExpand}
              setSelectedCategory={onSelectCategory}
              setEditingCategory={onEditCategory}
              setShowCategoryModal={onShowCategoryModal}
              handleDeleteCategory={onDeleteCategory}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
