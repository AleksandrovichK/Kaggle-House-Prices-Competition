import sys
import warnings

import pandas as pd
import numpy as np

from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV, LassoCV, ElasticNetCV
from sklearn.preprocessing import OneHotEncoder, StandardScaler, RobustScaler
from sklearn.preprocessing import LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline, make_pipeline
from scipy.stats import skew
from xgboost import XGBRegressor

from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score, KFold

print("Imports have been set")

# Disabling warnings
if not sys.warnoptions:
    warnings.simplefilter("ignore")

# Reading the training/val data and the test data
X = pd.read_csv('../input/house-prices-advanced-regression-techniques/train.csv', index_col='Id')
X_test = pd.read_csv('../input/house-prices-advanced-regression-techniques/test.csv', index_col='Id')

# Rows before:
rows_before = X.shape[0]
X.dropna(axis=0, subset=['SalePrice'], inplace=True)
rows_after = X.shape[0]
print("\nRows containing NaN in SalePrice were dropped: " + str(rows_before - rows_after))

# Logarithming target variable in order to make distribution better
X['SalePrice'] = np.log1p(X['SalePrice'])

y = X['SalePrice'].reset_index(drop=True)
train_features = X.drop(['SalePrice'], axis=1)

# concatenate the train and the test set as features for tranformation to avoid mismatch
features = pd.concat([train_features, X_test]).reset_index(drop=True)
print('\nFeatures size:', features.shape)

nan_count_table = (features.isnull().sum())
nan_count_table = nan_count_table[nan_count_table > 0].sort_values(ascending=False)
print("\nColums containig NaN: ")
print(nan_count_table)

columns_containig_nan = nan_count_table.index.to_list()
print("\nWhat values they contain: ")
print(features[columns_containig_nan])

# ==============================================
# FEATURE ENGINEERING
# Let's perform feature engineering for each column checking what it is and filling gaps / nans
# ==============================================
for column in columns_containig_nan:

    # populating with 0
    if column in ['GarageYrBlt', 'GarageArea', 'GarageCars', 'BsmtFinSF1', 'BsmtFinSF2', 'BsmtUnfSF', '1stFlrSF', '2ndFlrSF', 'LowQualFinSF',
                  'GrLivArea', 'BsmtFullBath', 'BsmtHalfBath', 'FullBath', 'HalfBath', 'BedroomAbvGr', 'KitchenAbvGr', 'TotRmsAbvGrd', 'TotalBsmtSF',
                  'Fireplaces', 'WoodDeckSF', 'OpenPorchSF', 'EnclosedPorch', '3SsnPorch', 'ScreenPorch', 'PoolArea', 'MiscVal', 'MoSold', 'YrSold',
                  'OverallQual', 'OverallCond', 'YearBuilt', 'YearRemodAdd', 'MasVnrArea']:
        features[column] = features[column].fillna(0)

    # populate with 'None'
    if column in ['GarageType', 'GarageFinish', 'GarageQual', 'GarageCond', "PoolQC", 'BsmtQual', 'BsmtCond', 'BsmtExposure', 'BsmtFinType1',
                  'BsmtFinType2', 'Neighborhood', 'BldgType', 'HouseStyle', 'MasVnrType', 'FireplaceQu', 'Fence', 'MiscFeature']:
        features[column] = features[column].fillna('None')

    # populate with most frequent value for cateforic
    if column in ['Street', 'LotShape', 'LandContour', 'Utilities', 'LotConfig', 'LandSlope', 'Condition1', 'Condition2', 'RoofStyle',
                  'Electrical', 'Functional', 'KitchenQual', 'Exterior1st', 'Exterior2nd', 'SaleType', 'RoofMatl', 'ExterQual', 'ExterCond',
                  'Foundation', 'Heating', 'HeatingQC', 'CentralAir', 'Electrical', 'KitchenQual', 'PavedDrive', 'SaleType', 'SaleCondition']:
        features[column] = features[column].fillna(features[column].mode()[0])

# MSSubClass: Numeric feature. Identifies the type of dwelling involved in the sale.
#     20  1-STORY 1946 & NEWER ALL STYLES
#     30  1-STORY 1945 & OLDER
#     40  1-STORY W/FINISHED ATTIC ALL AGES
#     45  1-1/2 STORY - UNFINISHED ALL AGES
#     50  1-1/2 STORY FINISHED ALL AGES
#     60  2-STORY 1946 & NEWER
#     70  2-STORY 1945 & OLDER
#     75  2-1/2 STORY ALL AGES
#     80  SPLIT OR MULTI-LEVEL
#     85  SPLIT FOYER
#     90  DUPLEX - ALL STYLES AND AGES
#    120  1-STORY PUD (Planned Unit Development) - 1946 & NEWER
#    150  1-1/2 STORY PUD - ALL AGES
#    160  2-STORY PUD - 1946 & NEWER
#    180  PUD - MULTILEVEL - INCL SPLIT LEV/FOYER
#    190  2 FAMILY CONVERSION - ALL STYLES AND AGES

# Stored as number so converted to string.
features['MSSubClass'] = features['MSSubClass'].apply(str)
features["MSSubClass"] = features["MSSubClass"].fillna("Unknown")
# MSZoning: Identifies the general zoning classification of the sale.
#    A    Agriculture
#    C    Commercial
#    FV   Floating Village Residential
#    I    Industrial
#    RH   Residential High Density
#    RL   Residential Low Density
#    RP   Residential Low Density Park
#    RM   Residential Medium Density

# 'RL' is by far the most common value. So we can fill in missing values with 'RL'
features['MSZoning'] = features.groupby('MSSubClass')['MSZoning'].transform(lambda x: x.fillna(x.mode()[0]))
# LotFrontage: Linear feet of street connected to property
# Groupped by neighborhood and filled in missing value by the median LotFrontage of all the neighborhood
# TODO may be 0 would perform better than median?
features['LotFrontage'] = features.groupby('Neighborhood')['LotFrontage'].transform(lambda x: x.fillna(x.median()))
# LotArea: Lot size in square feet.
# Stored as string so converted to int.
features['LotArea'] = features['LotArea'].astype(np.int64)
# Alley: Type of alley access to property
#    Grvl Gravel
#    Pave Paved
#    NA   No alley access

# So. If 'Street' made of 'Pave', so it would be reasonable to assume that 'Alley' might be 'Pave' as well.
features['Alley'] = features['Alley'].fillna('Pave')
# MasVnrArea: Masonry veneer area in square feet
# Stored as string so converted to int.
features['MasVnrArea'] = features['MasVnrArea'].astype(np.int64)

# ==============================
#      ADDING NEW FEATURES
# ==============================
features['YrBltAndRemod'] = features['YearBuilt'] + features['YearRemodAdd']
features['TotalSF'] = features['TotalBsmtSF'] + features['1stFlrSF'] + features['2ndFlrSF']

features['Total_sqr_footage'] = (features['BsmtFinSF1'] + features['BsmtFinSF2'] +
                                 features['1stFlrSF'] + features['2ndFlrSF'])

features['Total_Bathrooms'] = (features['FullBath'] + (0.5 * features['HalfBath']) +
                               features['BsmtFullBath'] + (0.5 * features['BsmtHalfBath']))

features['Total_porch_sf'] = (features['OpenPorchSF'] + features['3SsnPorch'] +
                              features['EnclosedPorch'] + features['ScreenPorch'] +
                              features['WoodDeckSF'])

# If area is not 0 so creating new feature looks reasonable
features['haspool'] = features['PoolArea'].apply(lambda x: 1 if x > 0 else 0)
features['has2ndfloor'] = features['2ndFlrSF'].apply(lambda x: 1 if x > 0 else 0)
features['hasgarage'] = features['GarageArea'].apply(lambda x: 1 if x > 0 else 0)
features['hasbsmt'] = features['TotalBsmtSF'].apply(lambda x: 1 if x > 0 else 0)
features['hasfireplace'] = features['Fireplaces'].apply(lambda x: 1 if x > 0 else 0)

print('Features size:', features.shape)

nan_count_train_table = (features.isnull().sum())
nan_count_train_table = nan_count_train_table[nan_count_train_table > 0].sort_values(ascending=False)
print("\nAre no NaN here now: " + str(nan_count_train_table.size == 0))
# ============================================
#       FIXING SKEWED VALUES
# ============================================
numeric_columns = [cname for cname in features.columns if features[cname].dtype in ['int64', 'float64']]
print("\nColumns which are numeric: " + str(len(numeric_columns)) + " out of " + str(features.shape[1]))
print(numeric_columns)
categoric_columns = [cname for cname in features.columns if features[cname].dtype == "object"]
print("\nColumns whice are categoric: " + str(len(categoric_columns)) + " out of " + str(features.shape[1]))
print(categoric_columns)

skewness = features[numeric_columns].apply(lambda x: skew(x))
print(skewness.sort_values(ascending=False))

skewness = skewness[abs(skewness) > 0.5]
features[skewness.index] = np.log1p(features[skewness.index])
print("\nSkewed values: " + str(skewness.index))

# Kind of One-Hot encoding
final_features = pd.get_dummies(features).reset_index(drop=True)

# Spliting the data back to train(X,y) and test(X_sub)
X = final_features.iloc[:len(y), :]
X_test = final_features.iloc[len(X):, :]
print('Features size for train(X,y) and test(X_test):')
print('X', X.shape, 'y', y.shape, 'X_test', X_test.shape)

# ==============================================
#                      ML part
# ==============================================

# check maybe 10 kfolds would be better
kfolds = KFold(n_splits=5, shuffle=True, random_state=42)


# model scoring and validation function
def cv_rmse(the_model, x):
    return np.sqrt(-cross_val_score(the_model, x, y, scoring="neg_mean_squared_error", cv=kfolds))


# rmsle scoring function
def rmsle(y_actual, y_pred):
    return np.sqrt(mean_squared_error(y_actual, y_pred))


# setup models hyperparameters using a pipline
# The purpose of the pipeline is to assemble several steps that can be cross-validated together, while setting different parameters.
# This is a range of values that the model considers each time in runs a CV
e_alphas = [0.0001, 0.0002, 0.0003, 0.0004, 0.0005, 0.0006, 0.0007]
e_l1ratio = [0.8, 0.85, 0.9, 0.95, 0.99, 1]
alphas_alt = [14.5, 14.6, 14.7, 14.8, 14.9, 15, 15.1, 15.2, 15.3, 15.4, 15.5]
alphas2 = [5e-05, 0.0001, 0.0002, 0.0003, 0.0004, 0.0005, 0.0006, 0.0007, 0.0008]

# Kernel Ridge Regression : made robust to outliers
ridge = make_pipeline(RobustScaler(), RidgeCV(alphas=alphas_alt, cv=kfolds))

# LASSO Regression : made robust to outliers
lasso = make_pipeline(RobustScaler(), LassoCV(max_iter=1e7, alphas=alphas2, random_state=14, cv=kfolds))

# Elastic Net Regression : made robust to outliers
elasticnet = make_pipeline(RobustScaler(), ElasticNetCV(max_iter=1e7, alphas=e_alphas, cv=kfolds, l1_ratio=e_l1ratio))

# optimal parameters, received from CV
c_grid = {"n_estimators": [1000],
          "early_stopping_rounds": [1],
          "learning_rate": [0.1]}
xgb_regressor = XGBRegressor(objective='reg:squarederror')
cross_validation = KFold(n_splits=5, shuffle=True, random_state=2)
xgb_r = GridSearchCV(estimator=xgb_regressor,
                     param_grid=c_grid,
                     cv=cross_validation)

# Fit the training data X, y
print('\n\nFitting our models ensemble')
print('Elasticnet is fitting now...')
elastic_model = elasticnet.fit(X, y)
print('Lasso is fitting now...')
lasso_model = lasso.fit(X, y)
print('Ridge is fitting now...')
ridge_model = ridge.fit(X, y)
print('XGB is fitting now...')
xgb_model = xgb_r.fit(X, y)

# get the performance of each model on training data(validation set)
print('\n\nModels evaluating: ')
score = cv_rmse(ridge_model, X)
print("Ridge score: {:.4f} ({:.4f})\n".format(score.mean(), score.std()))

score = cv_rmse(lasso_model, X)
print("Lasso score: {:.4f} ({:.4f})\n".format(score.mean(), score.std()))

score = cv_rmse(elastic_model, X)
print("ElasticNet score: {:.4f} ({:.4f})\n".format(score.mean(), score.std()))

score = cv_rmse(xgb_model, X)
print("xgb_r score: {:.4f} ({:.4f})\n".format(score.mean(), score.std()))


# TODO make weghted sum
def blend_models(x):
    return ((elastic_model.predict(x)) + (lasso_model.predict(x)) + (ridge_model.predict(x)) + xgb_r.predict(x)) / 4


print('\nRMSLE score on train data:')
print(rmsle(y, blend_models(X)))

# submission = pd.read_csv("../input/house-prices-advanced-regression-techniques/sample_submission.csv")
# submission.iloc[:, 1] = np.expm1(blend_models(X_test))
# submission.to_csv("submission.csv", index=False)
