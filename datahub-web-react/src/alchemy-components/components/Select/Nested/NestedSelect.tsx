import React, { useCallback, useEffect, useRef, useState } from 'react';
import styled from 'styled-components';
import { Icon, Pill, colors } from '@components';

import {
    ActionButtonsContainer,
    Container,
    Dropdown,
    OptionList,
    Placeholder,
    SearchIcon,
    SearchInput,
    SearchInputContainer,
    SelectBase,
    SelectLabel,
    StyledClearButton,
} from '../components';

import { SelectSizeOptions } from '../types';
import { NestedOption } from './NestedOption';
import { SelectOption } from './types';

const NO_PARENT_VALUE = 'no_parent_value';

const LabelDisplayWrapper = styled.div`
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    max-height: 125px;
    min-height: 16px;
`;
const StyledCountBadgeContainer = styled.div`
    display: flex;
    align-items: center;
    gap: 4px;
    color: ${colors.gray[1800]};
`;

interface SelectLabelDisplayProps {
    selectedOptions: SelectOption[];
    placeholder: string;
    handleOptionChange: (node: SelectOption) => void;
    showCount?: boolean;
}

const SelectLabelDisplay = ({
    selectedOptions,
    placeholder,
    handleOptionChange,
    showCount,
}: SelectLabelDisplayProps) => {
    return (
        <LabelDisplayWrapper>
            {showCount && selectedOptions.length > 0 ? (
                <StyledCountBadgeContainer>
                    {placeholder}
                    <Pill label={`${selectedOptions.length}`} size="sm" variant="filled" />
                </StyledCountBadgeContainer>
            ) : (
                !!selectedOptions.length &&
                selectedOptions.map((o) => (
                    <Pill
                        label={o.label}
                        rightIcon="Close"
                        size="sm"
                        onClickRightIcon={(e) => {
                            e.stopPropagation();
                            handleOptionChange(o);
                        }}
                    />
                ))
            )}
            {!selectedOptions.length && <Placeholder>{placeholder}</Placeholder>}
        </LabelDisplayWrapper>
    );
};

export interface ActionButtonsProps {
    fontSize?: SelectSizeOptions;
    selectedOptions: SelectOption[];
    isOpen: boolean;
    isDisabled: boolean;
    isReadOnly: boolean;
    handleClearSelection: () => void;
    showCount?: boolean;
}

const SelectActionButtons = ({
    selectedOptions,
    isOpen,
    isDisabled,
    isReadOnly,
    handleClearSelection,
    fontSize = 'md',
    showCount = false,
}: ActionButtonsProps) => {
    return (
        <ActionButtonsContainer>
            {!showCount && !!selectedOptions.length && !isDisabled && !isReadOnly && (
                <StyledClearButton
                    icon={{ icon: 'Close', source: 'material', size: 'lg' }}
                    isCircle
                    onClick={handleClearSelection}
                    size={fontSize}
                    data-testid="dropdown-option-clear-icon"
                />
            )}
            <Icon icon="CaretDown" source="phosphor" rotate={isOpen ? '180' : '0'} size="md" color="gray" />
        </ActionButtonsContainer>
    );
};

export interface SelectProps {
    options: SelectOption[];
    label: string;
    value?: string;
    initialValues?: SelectOption[];
    onCancel?: () => void;
    onUpdate?: (selectedValues: SelectOption[]) => void;
    size?: SelectSizeOptions;
    showSearch?: boolean;
    isDisabled?: boolean;
    isReadOnly?: boolean;
    isRequired?: boolean;
    isMultiSelect?: boolean;
    areParentsSelectable?: boolean;
    loadData?: (node: SelectOption) => void;
    onSearch?: (query: string) => void;
    width?: number | 'full';
    height?: number;
    placeholder?: string;
    searchPlaceholder?: string;
    isLoadingParentChildList?: boolean;
    showCount?: boolean;
    shouldAlwaysSyncParentValues?: boolean;
    hideParentCheckbox?: boolean;
    implicitlySelectChildren?: boolean;
}

export const selectDefaults: SelectProps = {
    options: [],
    label: '',
    size: 'md',
    showSearch: false,
    isDisabled: false,
    isReadOnly: false,
    isRequired: false,
    isMultiSelect: false,
    width: 255,
    height: 425,
};

export const NestedSelect = ({
    options = selectDefaults.options,
    label = selectDefaults.label,
    initialValues = [],
    onUpdate,
    loadData,
    onSearch,
    showSearch = selectDefaults.showSearch,
    isDisabled = selectDefaults.isDisabled,
    isReadOnly = selectDefaults.isReadOnly,
    isRequired = selectDefaults.isRequired,
    isMultiSelect = selectDefaults.isMultiSelect,
    size = selectDefaults.size,
    areParentsSelectable = true,
    placeholder,
    searchPlaceholder,
    height = selectDefaults.height,
    isLoadingParentChildList = false,
    showCount = false,
    shouldAlwaysSyncParentValues = false,
    hideParentCheckbox = false,
    implicitlySelectChildren = true,
    ...props
}: SelectProps) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [isOpen, setIsOpen] = useState(false);
    const [selectedOptions, setSelectedOptions] = useState<SelectOption[]>(initialValues);
    const selectRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (initialValues && shouldAlwaysSyncParentValues) {
            // Check if selectedOptions and initialValues are different
            const areDifferent = JSON.stringify(selectedOptions) !== JSON.stringify(initialValues);

            if (initialValues && areDifferent) {
                setSelectedOptions(initialValues);
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [initialValues]);

    // TODO: handle searching inside of a nested component on the FE only

    const handleDocumentClick = useCallback((e: MouseEvent) => {
        if (selectRef.current && !selectRef.current.contains(e.target as Node)) {
            setIsOpen(false);
        }
    }, []);

    useEffect(() => {
        document.addEventListener('click', handleDocumentClick);
        return () => {
            document.removeEventListener('click', handleDocumentClick);
        };
    }, [handleDocumentClick]);

    const handleSelectClick = useCallback(() => {
        if (!isDisabled && !isReadOnly) {
            setIsOpen((prev) => !prev);
        }
    }, [isDisabled, isReadOnly]);

    const handleSearch = useCallback(
        (query: string) => {
            setSearchQuery(query);
            onSearch?.(query);
        },
        [onSearch],
    );

    // Instead of calling the update function individually whenever selectedOptions changes,
    // we use the useEffect hook to trigger the onUpdate function automatically when selectedOptions is updated.
    useEffect(() => {
        if (onUpdate) {
            onUpdate(selectedOptions);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedOptions]);

    const handleOptionChange = useCallback(
        (option: SelectOption) => {
            let newSelectedOptions: SelectOption[];
            if (selectedOptions.find((o) => o.value === option.value)) {
                newSelectedOptions = selectedOptions.filter((o) => o.value !== option.value);
            } else {
                newSelectedOptions = [...selectedOptions, option];
            }
            setSelectedOptions(newSelectedOptions);
            if (!isMultiSelect) {
                setIsOpen(false);
            }
        },
        [selectedOptions, isMultiSelect],
    );

    const addOptions = useCallback(
        (optionsToAdd: SelectOption[]) => {
            const existingValues = new Set(selectedOptions.map((option) => option.value));
            const filteredOptionsToAdd = optionsToAdd.filter((option) => !existingValues.has(option.value));
            if (filteredOptionsToAdd.length) {
                const newSelectedOptions = [...selectedOptions, ...filteredOptionsToAdd];
                setSelectedOptions(newSelectedOptions);
            }
        },
        [selectedOptions],
    );

    const removeOptions = useCallback(
        (optionsToRemove: SelectOption[]) => {
            const newValues = selectedOptions.filter(
                (selectedOption) => !optionsToRemove.find((o) => o.value === selectedOption.value),
            );
            setSelectedOptions(newValues);
        },
        [selectedOptions],
    );

    const handleClearSelection = useCallback(() => {
        setSelectedOptions([]);
        setIsOpen(false);
        if (onUpdate) {
            onUpdate([]);
        }
    }, [onUpdate]);

    // generate map for options to quickly fetch children
    const parentValueToOptions: { [parentValue: string]: SelectOption[] } = {};
    options.forEach((o) => {
        const parentValue = o.parentValue || NO_PARENT_VALUE;
        parentValueToOptions[parentValue] = parentValueToOptions[parentValue]
            ? [...parentValueToOptions[parentValue], o]
            : [o];
    });

    const rootOptions = parentValueToOptions[NO_PARENT_VALUE] || [];

    return (
        <Container ref={selectRef} size={size || 'md'} width={props.width || 255}>
            {label && <SelectLabel onClick={handleSelectClick}>{label}</SelectLabel>}
            <SelectBase
                isDisabled={isDisabled}
                isReadOnly={isReadOnly}
                isRequired={isRequired}
                isOpen={isOpen}
                onClick={handleSelectClick}
                fontSize={size}
                data-testid="nested-options-dropdown-container"
                width={props.width}
                {...props}
            >
                <SelectLabelDisplay
                    selectedOptions={selectedOptions}
                    placeholder={placeholder || 'Select an option'}
                    handleOptionChange={handleOptionChange}
                    showCount={showCount}
                />
                <SelectActionButtons
                    selectedOptions={selectedOptions}
                    isOpen={isOpen}
                    isDisabled={!!isDisabled}
                    isReadOnly={!!isReadOnly}
                    handleClearSelection={handleClearSelection}
                    fontSize={size}
                    showCount={showCount}
                />
            </SelectBase>
            {isOpen && (
                <Dropdown style={{ maxHeight: height, overflow: 'auto' }}>
                    {showSearch && (
                        <SearchInputContainer>
                            <SearchInput
                                type="text"
                                placeholder={searchPlaceholder || 'Search...'}
                                value={searchQuery}
                                onChange={(e) => handleSearch(e.target.value)}
                                style={{ fontSize: size || 'md', width: '100%' }}
                            />
                            <SearchIcon icon="Search" size={size} color="gray" />
                        </SearchInputContainer>
                    )}
                    <OptionList>
                        {rootOptions.map((option) => {
                            const isParentOptionLabelExpanded = selectedOptions.find(
                                (opt) => opt.parentValue === option.value,
                            );
                            return (
                                <NestedOption
                                    key={option.value}
                                    selectedOptions={selectedOptions}
                                    option={option}
                                    parentValueToOptions={parentValueToOptions}
                                    handleOptionChange={handleOptionChange}
                                    addOptions={addOptions}
                                    removeOptions={removeOptions}
                                    loadData={loadData}
                                    isMultiSelect={isMultiSelect}
                                    setSelectedOptions={setSelectedOptions}
                                    areParentsSelectable={areParentsSelectable}
                                    isLoadingParentChildList={isLoadingParentChildList}
                                    hideParentCheckbox={hideParentCheckbox}
                                    isParentOptionLabelExpanded={!!isParentOptionLabelExpanded}
                                    implicitlySelectChildren={implicitlySelectChildren}
                                />
                            );
                        })}
                    </OptionList>
                </Dropdown>
            )}
        </Container>
    );
};
