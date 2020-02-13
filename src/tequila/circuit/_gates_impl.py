import typing
import copy
import numbers
from abc import ABC
from tequila import TequilaException
from tequila.objective.objective import Variable, FixedVariable, assign_variable
from tequila.hamiltonian import PauliString, QubitHamiltonian
from tequila.tools import number_to_string, list_assignement

# typing convenience shortcuts
UnionList = typing.Union[typing.Iterable[numbers.Integral], numbers.Integral]
UnionParam = typing.Union[Variable, FixedVariable]

class QGateImpl:

    @property
    def name(self):
        return self._name

    @property
    def target(self):
        return self._target

    @property
    def control(self):
        return self._control

    def __init__(self, name, target: UnionList, control: UnionList = None):
        self._name = name
        self._target = tuple(list_assignement(target))
        self._control = tuple(list_assignement(control))
        self.finalize()

    def copy(self):
        return copy.deepcopy(self)

    def dagger(self):
        """
        :return: return the hermitian conjugate of the gate.
        """

        return QGateImpl(name=copy.copy(self.name), target=self.target,
                         control=self.control)

    def is_controlled(self) -> bool:
        """
        :return: True if the gate is controlled
        """
        if self.control:
            return True
        else:
            return False

    def is_gaussian(self) -> bool:
        '''

        :return: True if the gate can be expressed as the complex exponential of a hermitian generator, AND has been compiled into said form.
        '''
        return False
    def is_parametrized(self) -> bool:
        """
        :return: True if the gate is parametrized
        """
        return False

    def is_single_qubit_gate(self) -> bool:
        """
        Convenience and easier to interpret
        :return: True if the Gate only acts on one qubit (not controlled)
        """
        return ((not self.control) and (len(self.target) == 1))

    def is_differentiable(self) -> bool:
        '''
        defaults to False, overwritten by ParametrizedGate
        '''
        return False

    def finalize(self):
        if not self.target:
            raise Exception('Received no targets upon initialization')
        if self.is_controlled():
            for c in self.target:
                if c in self.control:
                    raise Exception("control and target are the same qubit: " + self.__str__())

        # Set the active qubits
        if self.control:
            self.qubits = self.target + self.control
        else:
            self.qubits = self.target

        self.max_qubit = self.compute_max_qubit()

    def __str__(self):
        result = str(self.name) + "(target=" + str(self.target)
        if not self.is_single_qubit_gate():
            result += ", control=" + str(self.control)
        result += ")"
        return result

    def __repr__(self):
        """
        Todo: Add Nice stringification
        """
        return self.__str__()

    def compute_max_qubit(self):
        """
        :return: highest qubit index used by this gate
        """
        if self.control is None:
            return max(self.target)
        else:
            return max(self.target + self.control)

    def __eq__(self, other):
        if self.name != other.name:
            return False
        if self.target != other.target:
            return False
        if self.control != other.control:
            return False
        return True


class MeasurementImpl(QGateImpl):

    def __init__(self, name, target):
        super().__init__(name=name, target=tuple(sorted(list_assignement(target))))


class ParametrizedGateImpl(QGateImpl, ABC):
    '''
    the base class from which all parametrized gates inherit. User defined gates, when implemented, are liable to be members of this class directly.
    Has su
    '''

    def extract_variables(self):
        if hasattr(self.parameter, "extract_variables"):
            return self.parameter.extract_variables()
        else:
            return []

    def dagger(self):
        raise TequilaException("should not be called from ABC")

    @property
    def parameter(self):
        return self._parameter


    @parameter.setter
    def parameter(self, other):
        self.parameter = assign_variable(variable=other)

    def __init__(self, name, parameter: UnionParam, target: UnionList, control: UnionList = None):
        super().__init__(name=name, target=target, control=control)
        self._parameter = assign_variable(variable=parameter)

    def is_gaussian(self):
        return False

    def is_parametrized(self) -> bool:
        return True

    def is_differentiable(self) -> bool:
        """
        :return: True if the gate is differentiable
        """
        return True

    def __str__(self):
        result = str(self.name) + "(target=" + str(self.target)
        if not self.is_single_qubit_gate():
            result += ", control=" + str(self.control)

        result += ", parameter=" + str(self._parameter)
        result += ")"
        return result

    def __eq__(self, other):
        if not isinstance(other, ParametrizedGateImpl):
            return False
        if not super().__eq__(other):
            return False
        if self._parameter != other._parameter:
            return False
        return True


class RotationGateImpl(ParametrizedGateImpl):
    axis_to_string = {0: "x", 1: "y", 2: "z"}
    string_to_axis = {"x": 0, "y": 1, "z": 2}

    @staticmethod
    def get_name(axis):
        axis = RotationGateImpl.assign_axis(axis)
        return "R" + RotationGateImpl.axis_to_string[axis]

    @property
    def axis(self):
        return self._axis

    @axis.setter
    def axis(self, value):
        self._axis = self.assign_axis(value)

    @property
    def angle(self):
        return self.parameter

    @angle.setter
    def angle(self, other):
        self.parameter = other

    @property
    def shift(self):
        return 0.5

    def __ipow__(self, power, modulo=None):
        self.angle *= power
        return self

    def __pow__(self, power, modulo=None):
        result = copy.deepcopy(self)
        result.angle *= power
        return result

    def __init__(self, axis, angle, target: list, control: list = None):
        assert (angle is not None)
        super().__init__(name=self.get_name(axis=axis), parameter=angle, target=target, control=control)
        self._axis = self.assign_axis(axis)

    @staticmethod
    def assign_axis(axis):
        if axis in RotationGateImpl.string_to_axis:
            return RotationGateImpl.string_to_axis[axis]
        elif hasattr(axis, "lower") and axis.lower() in RotationGateImpl.string_to_axis:
            return RotationGateImpl.string_to_axis[axis.lower()]
        else:
            assert (axis in [0, 1, 2])
            return axis

    def dagger(self):
        result = copy.deepcopy(self)
        result._parameter = assign_variable(-self.angle)
        return result

    def is_gaussian(self):
        return True

class PhaseGateImpl(ParametrizedGateImpl):

    def __init__(self,phase,target: list, control, list= None):
        assert (phase is not None)
        super().__init__(name='Phase',parameter=phase,target=target,control=control)

    def dagger(self):
        result = copy.deepcopy(self)
        result._parameter = -self.angle
        return result

    @property
    def phase(self):
        return self.parameter

    @phase.setter
    def phase(self, other):
        self.parameter = other

    def __pow__(self, power, modulo=None):
        result = copy.deepcopy(self)
        result.phase *= power
        return result

    def is_gaussian(self):
        return True

    @property
    def shift(self):
        return 1.
class PowerGateImpl(ParametrizedGateImpl):

    @property
    def power(self):
            return self.parameter

    @power.setter
    def power(self, other):
        self.parameter = other

    def __init__(self, name, target: list, power=None, control: list = None):
        super().__init__(name=name, parameter=power, target=target, control=control)

    def dagger(self):
        result = copy.deepcopy(self)
        return result


class ExponentialPauliGateImpl(ParametrizedGateImpl):
    """
    Same convention as for rotation gates:
    Exp(-i angle/2 * paulistring)
    """

    @property
    def angle(self):
        return self.parameter

    def dagger(self):
        result = copy.deepcopy(self)
        result._parameter = -self.angle
        return result

    def __init__(self, paulistring: PauliString, angle: float, control: typing.List[int] = None):
        super().__init__(name="Exp-Pauli", target=tuple(t for t in paulistring.keys()), control=control, parameter=angle)
        self.paulistring = paulistring
        self.finalize()

    def __str__(self):
        result = str(self.name) + "(target=" + str(self.target)
        if not self.is_single_qubit_gate():
            result += ", control=" + str(self.control)

        result += ", parameter=" + str(self._parameter)
        result += ", paulistring=" + str(self.paulistring)
        result += ")"
        return result


class TrotterizedGateImpl(QGateImpl):

    def is_parametrized(self) -> bool:
        return True

    def extract_variables(self) -> typing.Dict[str, numbers.Number]:
        tmp = []
        for angle in self.angles:
            if hasattr(angle, "extract_variables"):
                tmp += angle.extract_variables()
        return list(set(tmp))

    @property
    def angles(self):
        return self._parameter

    @angles.setter
    def angles(self, other):
        self._parameter = other

    def __init__(self, generators: typing.Union[QubitHamiltonian, typing.List[QubitHamiltonian]],
                 steps: int = 1,
                 angles: typing.Union[list, numbers.Real, Variable] = None,
                 control: typing.Union[list, int] = None,
                 threshold: numbers.Real = 0.0,
                 join_components: bool = True,
                 randomize_component_order: bool = True,
                 randomize: bool = True):
        """
        :param generators: list of generators
        :param angles: coefficients for each generator
        :param steps: Trotter Steps
        :param control: control qubits
        :param threshold: neglect terms in the given Hamiltonians if their coefficients are below this threshold
        :param join_components: The generators are trotterized together. If False the first generator is trotterized, then the second etc
        Note that for steps==1 as well as len(generators)==1 this has no effect
        :param randomize_component_order: randomize the order in the generators order before trotterizing
        :param randomize: randomize the trotter decomposition of each generator
        """
        super().__init__(name="Trotterized", target=self.extract_targets(generators), control=control)
        self.generators = list_assignement(generators)
        self.angles = angles
        self.steps = steps
        self.threshold = threshold
        self.join_components = join_components
        self.randomize_component_order = randomize_component_order
        self.randomize = randomize
        self.finalize()

    def __str__(self):
        result = str(self.name) + "(target=" + str(self.target)
        if not self.is_single_qubit_gate():
            result += ", control=" + str(self.control)

        result += ", angles=" + str(self._parameter)
        result += ", generators=" + str(self.generators)
        result += ")"
        return result

    @staticmethod
    def extract_targets(generators):
        targets = []
        for g in generators:
            for ps in g.paulistrings:
                targets += [k for k in ps.keys()]
        return tuple(set(targets))

    def dagger(self):
        result = copy.deepcopy(self)
        angles = []
        for angle in self.angles:
            angles.append(-angle)
        result.angles=angles
        return result
