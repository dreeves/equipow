// Scratch exact-arithmetic experiment. GMP owns all copied row coefficients.
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <gmpxx.h>
#include <memory>
#include <new>
#include <vector>

namespace {
constexpr const char* capsule_name = "native672.Bound";
struct Invalid {};
struct PythonError {};

void require(bool ok) {
    if (!ok) throw Invalid{};
}

struct Decref {
    void operator()(PyObject* object) const { Py_XDECREF(object); }
};
using Ref = std::unique_ptr<PyObject, Decref>;

PyObject* checked(PyObject* object) {
    if (!object) throw PythonError{};
    return object;
}

Ref sequence(PyObject* object) {
    require(PyTuple_CheckExact(object) || PyList_CheckExact(object));
    return Ref(checked(PySequence_Fast(object, nullptr)));
}

long index(PyObject* object) {
    require(PyLong_CheckExact(object));
    int overflow = 0;
    long value = PyLong_AsLongAndOverflow(object, &overflow);
    require(overflow == 0 && value >= 0);
    return value;
}

void integer(PyObject* object, mpz_class& out) {
    require(PyLong_CheckExact(object));
    int overflow = 0;
    long small = PyLong_AsLongAndOverflow(object, &overflow);
    if (overflow == 0) {
        mpz_set_si(out.get_mpz_t(), small);
        return;
    }
    // Import an unsigned absolute magnitude; apply its original sign afterward.
    // No decimal conversion or private CPython representation is used.
    Ref magnitude(checked(PyNumber_Absolute(object)));
    constexpr int flags = Py_ASNATIVEBYTES_LITTLE_ENDIAN |
                          Py_ASNATIVEBYTES_UNSIGNED_BUFFER |
                          Py_ASNATIVEBYTES_REJECT_NEGATIVE;
    Py_ssize_t size = PyLong_AsNativeBytes(magnitude.get(), nullptr, 0, flags);
    if (size < 0) throw PythonError{};
    std::vector<unsigned char> bytes(static_cast<size_t>(size));
    Py_ssize_t copied = PyLong_AsNativeBytes(magnitude.get(), bytes.data(), size, flags);
    if (copied < 0) throw PythonError{};
    require(copied <= size);
    mpz_import(out.get_mpz_t(), bytes.size(), -1, 1, 0, 0, bytes.data());
    if (overflow < 0) mpz_neg(out.get_mpz_t(), out.get_mpz_t());
}

PyObject* python_integer(const mpz_class& value) {
    if (mpz_fits_slong_p(value.get_mpz_t()))
        return checked(PyLong_FromLong(mpz_get_si(value.get_mpz_t())));
    std::vector<unsigned char> bytes((mpz_sizeinbase(value.get_mpz_t(), 2) + 7) / 8);
    size_t count = 0;
    // GMP exports the absolute magnitude, including when value is negative.
    mpz_export(bytes.data(), &count, -1, 1, 0, 0, value.get_mpz_t());
    Ref result(checked(PyLong_FromUnsignedNativeBytes(bytes.data(), count,
                                                    Py_ASNATIVEBYTES_LITTLE_ENDIAN)));
    if (mpz_sgn(value.get_mpz_t()) < 0) return checked(PyNumber_Negative(result.get()));
    return result.release();
}

struct Term { size_t position; mpz_class coefficient; };
struct Row { std::vector<Term> terms; mpz_class constant; };
struct Bound {
    size_t size;
    std::vector<Row> rows;
};

void destroy(PyObject* capsule) {
    delete static_cast<Bound*>(PyCapsule_GetPointer(capsule, capsule_name));
}

// Catch every C++ exception before returning through the Python C API.
template<class F> PyObject* invoke(F function) {
    try { return function(); }
    catch (const Invalid&) { PyErr_SetNone(PyExc_AssertionError); }
    catch (const PythonError&) {}
    catch (const std::bad_alloc&) { PyErr_NoMemory(); }
    catch (...) { PyErr_SetNone(PyExc_RuntimeError); }
    return nullptr;
}

PyObject* prepare(PyObject*, PyObject* args) {
    return invoke([&]() -> PyObject* {
        PyObject *source, *dimension;
        if (!PyArg_ParseTuple(args, "OO", &source, &dimension)) throw PythonError{};
        auto bound = std::make_unique<Bound>();
        bound->size = static_cast<size_t>(index(dimension));
        Ref rows = sequence(source);
        const Py_ssize_t count = PySequence_Fast_GET_SIZE(rows.get());
        bound->rows.reserve(static_cast<size_t>(count));
        for (Py_ssize_t i = 0; i < count; ++i) {
            Ref pair = sequence(PySequence_Fast_GET_ITEM(rows.get(), i));
            require(PySequence_Fast_GET_SIZE(pair.get()) == 2);
            Row row;
            integer(PySequence_Fast_GET_ITEM(pair.get(), 1), row.constant);
            Ref terms = sequence(PySequence_Fast_GET_ITEM(pair.get(), 0));
            for (Py_ssize_t j = 0; j < PySequence_Fast_GET_SIZE(terms.get()); ++j) {
                Ref term = sequence(PySequence_Fast_GET_ITEM(terms.get(), j));
                require(PySequence_Fast_GET_SIZE(term.get()) == 2);
                Term entry;
                entry.position = static_cast<size_t>(index(PySequence_Fast_GET_ITEM(term.get(), 0)));
                require(entry.position < bound->size);
                integer(PySequence_Fast_GET_ITEM(term.get(), 1), entry.coefficient);
                row.terms.push_back(std::move(entry));
            }
            bound->rows.push_back(std::move(row));
        }
        PyObject* capsule = checked(PyCapsule_New(bound.get(), capsule_name, destroy));
        bound.release();
        return capsule;
    });
}

PyObject* evaluate(PyObject*, PyObject* args) {
    return invoke([&]() -> PyObject* {
        PyObject *capsule, *lower, *upper, *multipliers;
        if (!PyArg_ParseTuple(args, "OOOO", &capsule, &lower, &upper, &multipliers))
            throw PythonError{};
        require(PyCapsule_IsValid(capsule, capsule_name));
        const Bound& bound = *static_cast<Bound*>(PyCapsule_GetPointer(capsule, capsule_name));
        Ref lo = sequence(lower), hi = sequence(upper), n = sequence(multipliers);
        require(static_cast<size_t>(PySequence_Fast_GET_SIZE(lo.get())) == bound.size);
        require(static_cast<size_t>(PySequence_Fast_GET_SIZE(hi.get())) == bound.size);
        require(static_cast<size_t>(PySequence_Fast_GET_SIZE(n.get())) == bound.rows.size());
        std::vector<mpz_class> g(bound.size);
        mpz_class result, m, l, u, left, right;
        for (size_t i = 0; i < bound.rows.size(); ++i) {
            integer(PySequence_Fast_GET_ITEM(n.get(), static_cast<Py_ssize_t>(i)), m);
            const Row& row = bound.rows[i];
            mpz_addmul(result.get_mpz_t(), m.get_mpz_t(), row.constant.get_mpz_t());
            for (const Term& term : row.terms)
                mpz_submul(g[term.position].get_mpz_t(), m.get_mpz_t(), term.coefficient.get_mpz_t());
        }
        for (size_t p = 0; p < bound.size; ++p) {
            integer(PySequence_Fast_GET_ITEM(lo.get(), static_cast<Py_ssize_t>(p)), l);
            integer(PySequence_Fast_GET_ITEM(hi.get(), static_cast<Py_ssize_t>(p)), u);
            mpz_mul(left.get_mpz_t(), g[p].get_mpz_t(), l.get_mpz_t());
            mpz_mul(right.get_mpz_t(), g[p].get_mpz_t(), u.get_mpz_t());
            mpz_add(result.get_mpz_t(), result.get_mpz_t(),
                    mpz_cmp(left.get_mpz_t(), right.get_mpz_t()) < 0 ? left.get_mpz_t() : right.get_mpz_t());
        }
        return python_integer(result);
    });
}

PyMethodDef methods[] = {
    {"prepare", prepare, METH_VARARGS, nullptr},
    {"evaluate", evaluate, METH_VARARGS, nullptr},
    {nullptr, nullptr, 0, nullptr}
};
PyModuleDef module = {PyModuleDef_HEAD_INIT, "_native_bound", nullptr, -1, methods};
}  // namespace

PyMODINIT_FUNC PyInit__native_bound() { return PyModule_Create(&module); }
